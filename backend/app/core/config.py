from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://geocost:geocost_dev@localhost:5433/geocost"
    cors_origins: list[str] = ["http://localhost:5173"]
    app_version: str = "0.1.0"


settings = Settings()
