from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_ENV: str = "development"
    DATABASE_URL: str = "sqlite:///./data/bakke.db"
    REDIS_URL: str = "redis://localhost:6379/0"
    SECRET_KEY: str = "dev-secret-change-me"

    MAX_REASONING_ITERATIONS: int = 5
    MAX_HYPOTHESES: int = 60
    TOP_N_DEFAULT: int = 10
    UPLOAD_MAX_MB: int = 25
    VIDEO_OUTPUT_DIR: str = "./data/videos"
    STORAGE_PROVIDER: str = "local"
    DATA_DIR: str = "./data"

    # Auth
    FIREBASE_PROJECT_ID: str = ""
    FIREBASE_CLIENT_EMAIL: str = ""
    FIREBASE_PRIVATE_KEY: str = ""
    FIREBASE_CREDENTIAL_PATH: str = ""
    FIREBASE_STORAGE_BUCKET: str = ""

    # LLM / AI providers
    LLM_PROVIDER: str = "mock"
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    EMBEDDING_PROVIDER: str = "mock"
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    STT_PROVIDER: str = "mock"
    STT_MODEL: str = "whisper-1"
    VISION_PROVIDER: str = "mock"
    VIDEO_UNDERSTANDING_PROVIDER: str = "mock"

    # Video generation
    VIDEO_GENERATION_PROVIDER: str = "mock"
    VIDEO_GENERATION_API_KEY: str = ""
    VIDEO_GENERATION_MODEL: str = ""

    # Worker
    JOB_POLL_INTERVAL_SECONDS: float = 1.0

    @property
    def is_development(self) -> bool:
        return self.APP_ENV != "production"

    @property
    def is_llm_mock(self) -> bool:
        return self.LLM_PROVIDER.lower() == "mock" or not self.OPENAI_API_KEY

    @property
    def data_path(self) -> Path:
        p = Path(self.DATA_DIR)
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def uploads_path(self) -> Path:
        p = self.data_path / "uploads"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def video_path(self) -> Path:
        p = Path(self.VIDEO_OUTPUT_DIR)
        p.mkdir(parents=True, exist_ok=True)
        return p


@lru_cache
def get_settings() -> Settings:
    return Settings()
