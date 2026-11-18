"""FastAPI app: middleware (request id, logging, CSRF), error handlers, routers.

Run with: uvicorn app.main:create_app --factory
"""

import re
import secrets
import time
import uuid
from collections.abc import Callable

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.ai import make_summarizer
from app.config import Settings
from app.db import Base, make_engine, make_session_factory
from app.errors import FieldError
from app.github_app import GitHub
from app.github_public import PRLink, fetch_public_pr, make_pr_fetcher
from app.logging_setup import configure_logging, get_logger
from app.ratelimit import RateLimiter
from app.routes import auth as auth_routes
from app.routes import github as github_routes
from app.routes import summaries as summary_routes
from app.security import csrf_ok, ensure_csrf_cookie

log = get_logger("pr_summary.http")

_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
# Signed by GitHub instead of a CSRF token.
_CSRF_EXEMPT = {"/api/github/webhook"}
_UNSET = object()


def create_app(
    settings: Settings | None = None,
    summarizer: object = _UNSET,
    pr_fetcher: Callable[[PRLink], tuple[str, str]] = fetch_public_pr,
    github: GitHub | None = None,
) -> FastAPI:
    settings = settings or Settings()
    configure_logging(settings.log_level, settings.log_json)
    if not settings.secret_key:
        settings.secret_key = secrets.token_urlsafe(32)
        log.warning(
            "secret_key_generated", note="Set SECRET_KEY so sign-in state survives restarts."
        )

    engine = make_engine(settings.database_url)
    if settings.database_url.startswith("sqlite"):
        Base.metadata.create_all(engine)  # tests & quick local runs; Postgres uses Alembic

    if summarizer is _UNSET:
        summarizer = make_summarizer(
            settings.ai_provider,
            settings.anthropic_api_key,
            settings.gemini_api_key,
            settings.gemini_model,
        )
    github = github or GitHub(settings)

    app = FastAPI(title="PR Summary", docs_url=None, redoc_url=None)
    app.state.settings = settings
    app.state.session_factory = make_session_factory(engine)
    app.state.summarizer = summarizer
    app.state.github = github
    app.state.limiter = RateLimiter()

    # ------------------------------------------------------------ middleware
    @app.middleware("http")
    async def request_context(request: Request, call_next) -> Response:
        incoming = request.headers.get("x-request-id", "")
        rid = incoming if _REQUEST_ID.match(incoming) else uuid.uuid4().hex
        request.state.request_id = rid
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=rid)
        started = time.perf_counter()

        if (
            request.method not in ("GET", "HEAD", "OPTIONS")
            and request.url.path.startswith("/api/")
            and request.url.path not in _CSRF_EXEMPT
            and not csrf_ok(request)
        ):
            response: Response = JSONResponse(
                {"detail": "Your session expired. Reload the page and try again."}, status_code=403
            )
            log.warning("csrf_rejected", path=request.url.path)
        else:
            try:
                response = await call_next(request)
            except Exception:
                log.exception("unhandled_error", method=request.method, path=request.url.path)
                response = JSONResponse(
                    {"detail": "Something went wrong on our side. Nothing was posted to GitHub."},
                    status_code=500,
                )

        ensure_csrf_cookie(request, response, settings)
        response.headers["X-Request-ID"] = rid
        log.info(
            "request",
            method=request.method,
            path=request.url.path,  # never the query string: it can hold OAuth codes
            status=response.status_code,
            duration_ms=round((time.perf_counter() - started) * 1000, 1),
            user_id=getattr(request.state, "user_id", None),
        )
        structlog.contextvars.clear_contextvars()
        return response

    # ------------------------------------------------------------ errors
    @app.exception_handler(FieldError)
    async def field_error(_: Request, exc: FieldError) -> JSONResponse:
        return JSONResponse({"detail": exc.message, "fields": exc.fields}, status_code=exc.status)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        fields = {}
        for err in exc.errors():
            loc = [str(p) for p in err.get("loc", ()) if p not in ("body", "query", "path")]
            if loc:
                fields[loc[-1]] = "This value isn't valid."
        return JSONResponse(
            {"detail": "Some of what was sent isn't valid.", "fields": fields}, status_code=422
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        if exc.status_code >= 500:
            log.error("http_error", status=exc.status_code, detail=str(exc.detail))
        detail = exc.detail if isinstance(exc.detail, str) else "Request failed."
        return JSONResponse({"detail": detail}, status_code=exc.status_code)

    # ------------------------------------------------------------ routes
    @app.get("/api/health")
    def health() -> dict:
        return {"ok": True}

    app.include_router(summary_routes.build_router(make_pr_fetcher(github, pr_fetcher)))
    app.include_router(auth_routes.build_router(github))
    app.include_router(github_routes.build_router(github))
    return app
