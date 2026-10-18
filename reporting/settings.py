from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CONDUIT_", env_file=ROOT / ".env.local", extra="ignore"
    )
    admin_dsn: str = "postgresql://conduit:conduit_dev@127.0.0.1:55432/conduit"
    app_dsn: str = "postgresql://conduit_app:conduit_app_dev@127.0.0.1:55432/conduit"
    admin_token: str = "conduit-admin-token"
    admin_username: str = "sysadmin"
    output_dir: Path = ROOT / ".local" / "reports"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash-lite"


settings = Settings()
