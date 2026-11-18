from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All secrets come from backend env vars only. Never log them."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./dev.db"
    ai_provider: str = "gemini"  # "gemini" or "claude"
    anthropic_api_key: str | None = None
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-3.8-flash"
    enable_dev_tools: bool = False
    monthly_spend_cap_usd: float = 10.0
