from functools import lru_cache
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "PulseIQ Social Intelligence Platform"
    APP_VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api/v1"

    DATABASE_URL: str = "postgresql+psycopg://pulseiq:pulseiq_secret_2026@localhost:5480/pulseiq"
    REDIS_URL: str = "redis://localhost:6390/0"
    CELERY_BROKER_URL: str = "redis://localhost:6390/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6390/2"

    JWT_SECRET_KEY: str = "pulseiq-enterprise-jwt-secret-key-2026-change-in-prod"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    CORS_ORIGINS: str = "http://localhost:3080,http://localhost:5180,http://127.0.0.1:3080,http://127.0.0.1:5180"

    ENABLE_SENTENCE_TRANSFORMERS: bool = False
    SENTENCE_TRANSFORMER_MODEL: str = "all-MiniLM-L6-v2"
    DATA_DIR: str = "/app/data"
    SEED_RECORD_COUNT: int = 52000
    AUTO_SEED_ON_STARTUP: bool = True

    LIVE_EVENTS_CHANNEL: str = "pulseiq:live_events"

    @property
    def cors_origin_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
