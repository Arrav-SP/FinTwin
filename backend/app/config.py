from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://fintwin:change_me_locally@localhost:5432/fintwin"
    # Public mode (see backend/app/access.py). Off by default: a server on its owner's machine is unrestricted.
    public: bool = Field(default=False, validation_alias="FINTWIN_PUBLIC")
    base_url: str = Field(default="", validation_alias="FINTWIN_BASE_URL")
    github_client_id: str = Field(default="", validation_alias="GITHUB_CLIENT_ID")
    github_client_secret: str = Field(default="", validation_alias="GITHUB_CLIENT_SECRET")
    session_secret: str = Field(default="", validation_alias="FINTWIN_SESSION_SECRET")
    dev_login: str = Field(default="", validation_alias="FINTWIN_DEV_LOGIN")
    # A second PostgreSQL database that keeps site runs and models across restarts (backend/app/archive.py).
    archive_url: str = Field(default="", validation_alias="FINTWIN_ARCHIVE_URL")
    # Retraining on site runs (backend/app/ml/retrain.py): first at this many runs, then after each further batch.
    site_min_runs: int = Field(default=60, validation_alias="FINTWIN_SITE_MIN_RUNS")
    retrain_every: int = Field(default=25, validation_alias="FINTWIN_RETRAIN_EVERY")
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()

