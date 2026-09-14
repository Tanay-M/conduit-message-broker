from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CONDUIT_")

    app_dsn: str = "postgresql://conduit_app:conduit_app_dev@localhost:5433/conduit"
    admin_dsn: str = "postgresql://conduit:conduit_dev@localhost:5433/conduit"
    admin_token: str = "conduit-admin-token"


settings = Settings()
