from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All secrets come from backend env vars only. Never log them (see logging_setup)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./dev.db"

    # ---- AI
    ai_provider: str = "gemini"  # "gemini" or "claude"
    anthropic_api_key: str | None = None
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-3.8-flash"
    monthly_spend_cap_usd: float = 10.0
    reviews_per_repo_per_month: int = 50

    # ---- Logging
    log_level: str = "INFO"
    log_json: bool = True

    # ---- Web app / sessions
    app_base_url: str = "http://localhost:5180"  # where the browser sees the app
    # Signs short-lived cookies (OAuth state, anonymous run claims). Set SECRET_KEY in
    # production; if empty, a random one is made at startup (those cookies reset on restart).
    secret_key: str = ""
    cookie_secure: bool = True  # browsers accept Secure cookies on http://localhost too
    session_days: int = 14
    # Login/signup attempts per IP per 10 minutes; summaries per IP per hour when signed out.
    auth_rate_limit: int = 10
    anon_summary_rate_limit: int = 10

    # ---- GitHub App (all optional until you create the app; see README)
    github_app_id: str | None = None
    github_app_slug: str | None = None
    github_app_private_key: str | None = None  # PEM; "\n" escapes are accepted
    github_client_id: str | None = None
    github_client_secret: str | None = None
    github_webhook_secret: str | None = None

    @property
    def github_app_configured(self) -> bool:
        return bool(self.github_app_id and self.github_app_slug and self.github_app_private_key)

    @property
    def github_login_configured(self) -> bool:
        return bool(self.github_client_id and self.github_client_secret)

    @property
    def private_key_pem(self) -> str | None:
        key = self.github_app_private_key
        return key.replace("\\n", "\n") if key else None
