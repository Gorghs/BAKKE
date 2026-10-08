from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from pydantic_settings import BaseSettings, SettingsConfigDict

# ---------------------------------------------------------------------------
# Generic provider configuration
#
# Every AI capability is configured with the same four values:
#
#   <PREFIX>_PROVIDER_TYPE   # "" (unset) | mock | http_chat | <adapter id>
#   <PREFIX>_API_BASE_URL    # base URL of the provider's HTTP API
#   <PREFIX>_API_KEY         # API key / bearer token
#   <PREFIX>_MODEL           # model identifier
#
# The core application never names a vendor: concrete adapters are selected
# by PROVIDER_TYPE through the adapter catalogue (app.adapters.providers).
# Legacy environment names (OPENAI_API_KEY, LLM_PROVIDER, ...) remain
# supported through the compatibility layer below.
# ---------------------------------------------------------------------------

_LEGACY_TYPE_MAP = {"openai": "http_chat"}

# Backward-compat default base URL used ONLY when a legacy OPENAI_API_KEY
# supplies the credential and no explicit base URL is configured.
_LEGACY_DEFAULT_BASE_URL = "https://api.openai.com/v1"


@dataclass(frozen=True)
class CapabilitySpec:
    """Describes the environment keys that configure one AI capability."""

    name: str
    prefix: str
    type_keys: tuple[str, ...]
    api_key_keys: tuple[str, ...]
    model_keys: tuple[str, ...]
    base_url_keys: tuple[str, ...] = ()
    default_type: str = "mock"
    default_model: str = ""

    @property
    def generic_type_key(self) -> str:
        return f"{self.prefix}_PROVIDER_TYPE"

    @property
    def generic_api_key_key(self) -> str:
        return f"{self.prefix}_API_KEY"

    @property
    def generic_base_url_key(self) -> str:
        return f"{self.prefix}_API_BASE_URL"

    @property
    def generic_model_key(self) -> str:
        return f"{self.prefix}_MODEL"


CAPABILITIES: dict[str, CapabilitySpec] = {
    spec.name: spec
    for spec in [
        CapabilitySpec(
            name="text",
            prefix="LLM",
            type_keys=("LLM_PROVIDER_TYPE", "LLM_PROVIDER"),
            api_key_keys=("LLM_API_KEY", "OPENAI_API_KEY"),
            model_keys=("LLM_MODEL", "OPENAI_MODEL"),
            base_url_keys=("LLM_API_BASE_URL",),
            default_model="",
        ),
        CapabilitySpec(
            name="embeddings",
            prefix="EMBEDDING",
            type_keys=("EMBEDDING_PROVIDER_TYPE", "EMBEDDING_PROVIDER"),
            api_key_keys=("EMBEDDING_API_KEY", "OPENAI_API_KEY"),
            model_keys=("EMBEDDING_MODEL",),
            base_url_keys=("EMBEDDING_API_BASE_URL",),
            default_model="",
        ),
        CapabilitySpec(
            name="speech",
            prefix="STT",
            type_keys=("STT_PROVIDER_TYPE", "STT_PROVIDER"),
            api_key_keys=("STT_API_KEY", "OPENAI_API_KEY"),
            model_keys=("STT_MODEL",),
            base_url_keys=("STT_API_BASE_URL",),
            default_model="whisper-1",
        ),
        CapabilitySpec(
            name="vision",
            prefix="VISION",
            type_keys=("VISION_PROVIDER_TYPE", "VISION_PROVIDER"),
            api_key_keys=("VISION_API_KEY", "OPENAI_API_KEY"),
            model_keys=("VISION_MODEL", "OPENAI_MODEL"),
            base_url_keys=("VISION_API_BASE_URL",),
            default_model="",
        ),
        CapabilitySpec(
            name="video_understanding",
            prefix="VIDEO_UNDERSTANDING",
            type_keys=("VIDEO_UNDERSTANDING_PROVIDER_TYPE", "VIDEO_UNDERSTANDING_PROVIDER"),
            api_key_keys=("VIDEO_UNDERSTANDING_API_KEY", "OPENAI_API_KEY"),
            model_keys=("VIDEO_UNDERSTANDING_MODEL", "OPENAI_MODEL"),
            base_url_keys=("VIDEO_UNDERSTANDING_API_BASE_URL",),
            default_model="",
        ),
        CapabilitySpec(
            name="video_generation",
            prefix="VIDEO_GENERATION",
            type_keys=("VIDEO_GENERATION_PROVIDER_TYPE", "VIDEO_GENERATION_PROVIDER"),
            api_key_keys=("VIDEO_GENERATION_API_KEY",),
            model_keys=("VIDEO_GENERATION_MODEL",),
            base_url_keys=("VIDEO_GENERATION_API_BASE_URL",),
            default_model="",
        ),
    ]
}

# Environment keys that may be overridden at runtime (via the providers API).
RUNTIME_KEYS: list[str] = []
for _spec in CAPABILITIES.values():
    RUNTIME_KEYS.extend(
        [
            _spec.generic_type_key,
            _spec.generic_api_key_key,
            _spec.generic_base_url_key,
            _spec.generic_model_key,
        ]
    )
    RUNTIME_KEYS.extend(k for k in _spec.type_keys + _spec.api_key_keys + _spec.model_keys + _spec.base_url_keys if k not in RUNTIME_KEYS)

# Speech model is shared between generic and legacy spellings.
if "STT_MODEL" not in RUNTIME_KEYS:
    RUNTIME_KEYS.append("STT_MODEL")


class ConfigError(Exception):
    """Raised when mandatory configuration is missing or invalid."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors))


@dataclass(frozen=True)
class ResolvedCapability:
    """Fully resolved provider configuration for one capability."""

    name: str
    provider_type: str  # "" only when unset; otherwise "mock" | adapter id
    api_base_url: str
    api_key: str
    model: str
    source: str  # "runtime" | "env" | "legacy" | "default"

    @property
    def is_mock(self) -> bool:
        return self.provider_type in ("", "mock")

    @property
    def configured(self) -> bool:
        """True when this capability is set up to call a live provider."""
        if self.is_mock:
            return False
        return bool(self.api_key or self.api_base_url) and bool(self.model or self.api_base_url)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_ENV: str = "development"
    DATABASE_URL: str = "sqlite:///./data/bakke.db"
    REDIS_URL: str = "redis://localhost:6379/0"
    SECRET_KEY: str = "dev-secret-change-me"

    # Comma-separated list. Empty -> "*" in development, rejected in production.
    CORS_ALLOW_ORIGINS: str = ""

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

    # --- Generic provider configuration (see module docstring) -------------
    LLM_PROVIDER_TYPE: str = ""
    LLM_API_BASE_URL: str = ""
    LLM_API_KEY: str = ""
    LLM_MODEL: str = ""

    EMBEDDING_PROVIDER_TYPE: str = ""
    EMBEDDING_API_BASE_URL: str = ""
    EMBEDDING_API_KEY: str = ""
    EMBEDDING_MODEL: str = ""

    STT_PROVIDER_TYPE: str = ""
    STT_API_BASE_URL: str = ""
    STT_API_KEY: str = ""
    STT_MODEL: str = ""

    VISION_PROVIDER_TYPE: str = ""
    VISION_API_BASE_URL: str = ""
    VISION_API_KEY: str = ""
    VISION_MODEL: str = ""

    VIDEO_UNDERSTANDING_PROVIDER_TYPE: str = ""
    VIDEO_UNDERSTANDING_API_BASE_URL: str = ""
    VIDEO_UNDERSTANDING_API_KEY: str = ""
    VIDEO_UNDERSTANDING_MODEL: str = ""

    VIDEO_GENERATION_PROVIDER_TYPE: str = ""
    VIDEO_GENERATION_API_BASE_URL: str = ""
    VIDEO_GENERATION_API_KEY: str = ""
    VIDEO_GENERATION_MODEL: str = ""

    # --- Legacy names (compatibility only; see CAPABILITIES) ---------------
    LLM_PROVIDER: str = "mock"
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    EMBEDDING_PROVIDER: str = "mock"
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    STT_PROVIDER: str = "mock"
    VISION_PROVIDER: str = "mock"
    VIDEO_UNDERSTANDING_PROVIDER: str = "mock"
    VIDEO_GENERATION_PROVIDER: str = "mock"

    # Worker
    JOB_POLL_INTERVAL_SECONDS: float = 1.0

    @property
    def is_development(self) -> bool:
        return not self.is_production

    @property
    def is_production(self) -> bool:
        return self.APP_ENV.strip().lower() in ("production", "prod")

    @property
    def is_llm_mock(self) -> bool:
        return resolve_capability("text", self).is_mock

    def cors_origins(self) -> list[str]:
        raw = self.CORS_ALLOW_ORIGINS.strip()
        if not raw:
            return ["*"] if self.is_development else []
        return [o.strip() for o in raw.split(",") if o.strip()]

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


def _first_setting(keys: tuple[str, ...], settings: Settings) -> tuple[str, str]:
    """Return (value, key) for the first non-empty key on Settings.

    Values come from real environment variables *or* the .env file — both are
    loaded into Settings by pydantic-settings, so this is the single source
    for non-runtime configuration.
    """
    for key in keys:
        value = getattr(settings, key, "") or ""
        if value:
            return value, key
    return "", ""


def _normalize_type(raw: str) -> str:
    raw = (raw or "").strip().lower()
    return _LEGACY_TYPE_MAP.get(raw, raw)


def resolve_capability(name: str, settings: Settings | None = None, runtime_lookup=None) -> ResolvedCapability:
    """Resolve one capability's provider configuration.

    Precedence: runtime DB override -> generic env -> legacy env -> default.
    ``runtime_lookup`` is injectable for tests; by default the DB-backed
    runtime override store is used.
    """
    from app.adapters.persistence import runtime_config as _runtime  # lazy: avoids import cycle

    spec = CAPABILITIES[name]
    settings = settings or get_settings()
    lookup = runtime_lookup or _runtime.get_value

    def resolve(keys: tuple[str, ...], generic_key: str) -> tuple[str, str]:
        for key in (generic_key, *keys):
            value = lookup(key)
            if value:
                return value, "runtime"
        value, _ = _first_setting((generic_key, *keys), settings)
        if value:
            return value, "env" if value == getattr(settings, generic_key, "") else "legacy"
        return "", ""

    raw_type, type_source = resolve(spec.type_keys, spec.generic_type_key)
    provider_type = _normalize_type(raw_type) or spec.default_type

    api_key, key_source = resolve(spec.api_key_keys, spec.generic_api_key_key)
    model, model_source = resolve(spec.model_keys, spec.generic_model_key) or (spec.default_model, "default")
    base_url, base_source = resolve(spec.base_url_keys, spec.generic_base_url_key)

    if not base_url and provider_type not in ("", "mock") and key_source == "legacy" and "OPENAI_API_KEY" in spec.api_key_keys and api_key:
        base_url = _LEGACY_DEFAULT_BASE_URL
        if not model:
            model = spec.default_model

    source = "default"
    if type_source != "" or key_source != "" or model_source != "" or base_source != "":
        source = "runtime" if "runtime" in (type_source, key_source, model_source, base_source) else (
            "legacy" if "legacy" in (type_source, key_source, model_source, base_source) else "env"
        )

    return ResolvedCapability(
        name=name,
        provider_type=provider_type,
        api_base_url=base_url.rstrip("/"),
        api_key=api_key,
        model=model,
        source=source,
    )


def sanitize_base_url(value: str) -> str:
    """Strip userinfo (``user:password@``) before a base URL is echoed anywhere."""
    if "@" not in value:
        return value
    try:
        parts = urlsplit(value)
        if "@" not in parts.netloc:
            return value
        host = parts.hostname or ""
        if parts.port is not None:
            host = f"{host}:{parts.port}"
        return urlunsplit((parts.scheme, host, parts.path, parts.query, parts.fragment))
    except ValueError:
        # Unparseable netloc — keep only the tail so credentials never leak.
        return value.rsplit("@", 1)[-1]


def _base_url_errors(spec: CapabilitySpec, resolved: ResolvedCapability) -> list[str]:
    """Base URL safety rules shared by startup and pre-write validation."""
    if resolved.is_mock or not resolved.api_base_url:
        return []
    raw = resolved.api_base_url.strip()
    shown = sanitize_base_url(raw)
    try:
        parts = urlsplit(raw)
    except ValueError:
        parts = None
    if parts is None or parts.scheme not in ("http", "https"):
        return [
            f"{spec.generic_base_url_key} (capability '{spec.name}'): {shown!r} is not a valid base URL — "
            "must be an absolute http:// or https:// URL with a host"
        ]
    if not parts.netloc:
        return [
            f"{spec.generic_base_url_key} (capability '{spec.name}'): {shown!r} has no host — "
            "must be an absolute http:// or https:// URL"
        ]
    return []


def capability_config_errors(resolve: Callable[[str], ResolvedCapability]) -> list[str]:
    """Configuration errors for every capability under ``resolve`` (empty when valid).

    Shared by startup validation (:func:`validate_settings`) and the providers
    API pre-write check so both enforce exactly the same rules.
    """
    errors: list[str] = []
    for name, spec in CAPABILITIES.items():
        resolved = resolve(name)
        errors.extend(_base_url_errors(spec, resolved))
        if resolved.is_mock:
            continue
        if resolved.provider_type != "http_chat":
            # vendor/adapter-specific types are validated against the adapter
            # catalogue at startup (see adapters.providers.validate_provider_types)
            continue
        if not resolved.api_base_url:
            errors.append(f"{spec.generic_base_url_key}: required when {spec.generic_type_key}={resolved.provider_type}")
        if not resolved.api_key:
            errors.append(f"{spec.generic_api_key_key}: required when {spec.generic_type_key}={resolved.provider_type}")
        if not resolved.model:
            errors.append(f"{spec.generic_model_key}: required when {spec.generic_type_key}={resolved.provider_type}")
    return errors


_PLACEHOLDER_SECRET_KEYS = frozenset({"", "change-me-in-production", "change-me", "changeme"})


def validate_settings(settings: Settings | None = None) -> list[str]:
    """Return a list of configuration errors (empty when valid).

    Development stays permissive: misconfiguration is reported as a list so
    callers can log warnings. Production callers must treat non-empty results
    as fatal — BAKKE never silently falls back to mocks when live
    configuration is invalid.
    """
    s = settings or get_settings()
    errors = capability_config_errors(lambda name: resolve_capability(name, s, runtime_lookup=lambda _k: ""))

    if s.is_production:
        if s.SECRET_KEY == Settings.model_fields["SECRET_KEY"].default:
            errors.append("SECRET_KEY: must be set to a unique value in production")
        if s.SECRET_KEY.strip().lower() in _PLACEHOLDER_SECRET_KEYS or len(s.SECRET_KEY) < 16:
            errors.append("SECRET_KEY: set a strong SECRET_KEY in production (no placeholder or short value)")
        origins = s.cors_origins()
        if not origins:
            errors.append("CORS_ALLOW_ORIGINS: must be set explicitly in production")
        elif "*" in origins:
            errors.append("CORS_ALLOW_ORIGINS: wildcard is not allowed in production")
        if not (s.FIREBASE_PROJECT_ID and s.FIREBASE_CLIENT_EMAIL and s.FIREBASE_PRIVATE_KEY):
            errors.append(
                "authentication: no external auth configured — the built-in DEV user must not be used in production"
            )
        if not s.DATABASE_URL:
            errors.append("DATABASE_URL: required in production")
        elif s.DATABASE_URL == Settings.model_fields["DATABASE_URL"].default:
            errors.append("DATABASE_URL: package default is not allowed in production — set DATABASE_URL explicitly")

    return errors


@lru_cache
def get_settings() -> Settings:
    return Settings()
