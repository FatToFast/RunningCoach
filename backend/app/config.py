from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Garmin
    garmin_email: str = ""
    garmin_password: str = ""

    # OpenAI
    openai_api_key: str = ""

    # Database
    database_url: str = "sqlite:///./data/runningcoach.db"

    # App
    secret_key: str = "dev-secret-key"
    debug: bool = True

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
