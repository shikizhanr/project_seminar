from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Habit Coach"
    environment: str = "development"
    secret_key: str = "development-secret-key"
    database_url: str = "sqlite+aiosqlite:///./habit_coach.db"
    redis_url: str = "redis://localhost:6379/0"
    access_token_expire_minutes: int = 60 * 24 * 7
    cors_origins: list[str] | str = ["http://localhost:8081", "http://localhost:19006"]
    api_v1_prefix: str = "/api/v1"
    ollama_enabled: bool = False
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:0.6b"
    ollama_timeout_seconds: float = 30.0

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: object) -> object:
        if isinstance(value, str) and not value.startswith("["):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
