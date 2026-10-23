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
    OPENAI_BASE_URL: str = ""
    # Per-call upstream budgeting. Account-level rate limits (Gemini web,
    # BardErrorInfo 13 1155) punish bursts, so cap SDK retries and optionally
    # space consecutive upstream attempts apart.
    LLM_MAX_RETRIES: int = 6
    LLM_CALL_MIN_INTERVAL: float = 0.0
    # Upper bound on output tokens per call. 0 omits max_tokens, which leaves
    # the provider to decide. Some endpoints (Groq on-demand) reject a request
    # whose expected output exceeds their per-minute output budget, and without
    # max_tokens they assume a default (2048) far above that budget, so every
    # call is refused. Set this below the provider's output-tokens-per-minute
    # cap to make that provider usable. A task listed in
    # providers/llm.py::_TASK_OUTPUT_FLOOR raises this bound for its own call:
    # those tasks return one long string, and a cut completion cannot be
    # repaired from a partial.
    LLM_MAX_OUTPUT_TOKENS: int = 0
    # Reasoning-model endpoints (Groq gpt-oss) spend part of the completion
    # budget on hidden reasoning tokens before writing the reply. At the default
    # effort a 900-token call can return empty content with finish_reason
    # "length", because the reasoning alone used the budget. "low" keeps the
    # output for the answer. Empty omits the parameter, which non-reasoning
    # endpoints require.
    LLM_REASONING_EFFORT: str = ""
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
    # Base URL of a self-hosted gemini-web-to-api bridge (provider
    # "gemini-web"), e.g. http://host.docker.internal:4981.
    VIDEO_GENERATION_BASE_URL: str = ""
    # The scenario's visual brief (which actors, which objects change state,
    # which actions happen) may be filled by the LLM. Every label and verb it
    # returns has to appear in the scenario's own text, so it cannot invent
    # set dressing. Off, the deterministic extractor fills it instead.
    VIDEO_VISUAL_BRIEF: bool = True

    # Optional LLM rewrite of the director's visual prompt. Off by default: the
    # director prompt is authoritative and names only what the scenario states,
    # while the rewrite reliably invents set dressing (windows, lamps, materials)
    # that the spec's own "Do not add objects" constraint then contradicts.
    VIDEO_PROMPT_EXPANSION: bool = False

    # Worker
    JOB_POLL_INTERVAL_SECONDS: float = 1.0
    # A RUNNING job older than this is treated as an orphan from a crashed
    # worker and requeued. Pace-spaced LLM runs legitimately outlast 15 min, so
    # this must exceed the longest real run; raise it when pacing is slow.
    STALE_RUNNING_SECONDS: int = 900

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
