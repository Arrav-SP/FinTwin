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
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()

