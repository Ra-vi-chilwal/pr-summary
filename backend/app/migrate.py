"""Apply Alembic migrations at startup (Postgres only).

Vercel has no start command, so the app brings the schema up to date itself. A Postgres
advisory lock makes concurrent cold starts wait for each other instead of racing.
"""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, text

from app.logging_setup import get_logger

log = get_logger("pr_summary.migrate")

ALEMBIC_INI = Path(__file__).resolve().parent.parent / "alembic.ini"
_LOCK_ID = 727_001  # any constant shared by every instance of this app


def upgrade_to_head(engine: Engine) -> bool:
    """Returns True on success. Never raises: a failure is logged loudly instead."""
    if engine.dialect.name != "postgresql":
        return False
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT pg_advisory_lock(:id)"), {"id": _LOCK_ID})
            try:
                cfg = Config(str(ALEMBIC_INI))
                cfg.set_main_option(
                    "sqlalchemy.url",
                    engine.url.render_as_string(hide_password=False).replace("%", "%%"),
                )
                command.upgrade(cfg, "head")
            finally:
                conn.execute(text("SELECT pg_advisory_unlock(:id)"), {"id": _LOCK_ID})
                conn.commit()
        log.info("migrations_applied", revision="head")
        return True
    except Exception:
        log.exception("migrations_failed")
        return False
