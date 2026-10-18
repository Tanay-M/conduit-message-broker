from pydantic_settings import BaseSettings, SettingsConfigDict

from reporting.settings import ROOT


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CONDUIT_", env_file=ROOT / ".env.local", extra="ignore"
    )

    app_dsn: str = "postgresql://conduit_app:conduit_app_dev@127.0.0.1:55432/conduit"
    admin_dsn: str = "postgresql://conduit:conduit_dev@127.0.0.1:55432/conduit"
    admin_token: str = "conduit-admin-token"
    admin_username: str = "sysadmin"
    login_username: str = "admin"
    login_password: str = "Conduit@123"


settings = Settings()
