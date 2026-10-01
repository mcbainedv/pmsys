"""Application settings, read from environment / .env."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "PMSyS"
    database_url: str = "mysql+pymysql://pmsys:pmsys_secret@localhost:3306/pmsys"
    secret_key: str = "change-me-in-production"
    debug: bool = False

    # Default credentials created on first startup (Change these after first login).
    default_admin_username: str = "admin"
    default_admin_password: str = "admin"


settings = Settings()