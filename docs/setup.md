# Setup

## Prerequisites

- Docker + Docker Compose (recommended) **or** Python 3.12+ / Node 20+ run locally.
- ffmpeg/ffprobe on PATH for local video generation (`apt install ffmpeg` or Homebrew).
- Optional: API keys for live providers. Nothing else is required — the default
  configuration runs every capability as an explicit local mock.

## Quick start (Docker)

```bash
cp .env.example .env
docker compose up --build
```

| Service   | URL                               |
|-----------|-----------------------------------|
| API       | http://localhost:8000/docs        |
| Frontend  | http://localhost:3000             |
| Postgres  | localhost:5432 (`bakke`/`bakke`)  |
| Redis     | localhost:6380 (host port remapped; 6379 may be taken) |

The backend and the worker both run `alembic upgrade head` on startup, so the schema is
created automatically. Compose passes the generic `*_PROVIDER_*` keys from your `.env`
through to both containers.

Seed the demo case (7 evidence items: right-hip set + chest variant + video):

```bash
docker compose exec backend python -m scripts.seed_demo
```

## Run locally

```bash
cp .env.example .env                     # repo root; edit as needed

# venv + schema (from apps/backend)
cd apps/backend
python -m venv ../../.venv && ../../.venv/bin/pip install -r requirements.txt
set -a && source ../../.env && set +a     # export the config into this shell
../../.venv/bin/alembic upgrade head                          # migrations
../../.venv/bin/uvicorn app.main:app --port 8000              # API (shell 1)
../../.venv/bin/python -m app.infrastructure.jobs.worker      # worker (shell 2)
../../.venv/bin/python -m scripts.seed_demo                   # demo data (shell 3)
```

Makefile shortcuts from the repo root (`make api`, `make worker`, `make migrate`,
`make seed`, `make test`) already `include` and export the root `.env`, so no manual
export is needed. Docker Compose reads the same root `.env` for variable substitution
and passes the provider keys to both the backend and the worker.

Frontend (local):

```bash
cd apps/frontend
npm install
npm run dev            # http://localhost:3000
npm run build          # production build check
npm run lint           # next lint
```

## Configuration

Settings come from real environment variables plus a `.env` file in the process's
working directory (`apps/backend/app/config.py`, pydantic-settings).

**`.env.example` is the source of truth** for every key — copy it to `.env` and edit.
Two patterns to know:

- **Generic provider keys (preferred).** Each of the six capabilities takes the same four
  values — `<PREFIX>_PROVIDER_TYPE`, `<PREFIX>_API_BASE_URL`, `<PREFIX>_API_KEY`,
  `<PREFIX>_MODEL` — where `<PREFIX>` is `LLM`, `EMBEDDING`, `STT`, `VISION`,
  `VIDEO_UNDERSTANDING` or `VIDEO_GENERATION`. `PROVIDER_TYPE` is `mock` or an adapter
  id: `http_chat` for the first five, `mock | kling | runway | hailuo` for video
  generation. `http_chat` requires base URL, key and model.
- **Legacy names (deprecated, still honoured).** `OPENAI_API_KEY`, `OPENAI_MODEL`,
  `LLM_PROVIDER`, `<X>_PROVIDER` … are used only when the matching generic key is unset
  (`openai` is treated as `http_chat`). Prefer the generic keys for anything new.

Resolution precedence for every capability
(`resolve_capability`, `app/config.py`):

```
runtime DB override  →  generic env  →  legacy env  →  mock default
```

Runtime overrides are rows in `provider_settings`, written through `PUT /api/providers`
and applied without a restart; keys are stored masked in API responses.

Other keys: `DATABASE_URL`, `REDIS_URL`, `APP_ENV`, `CORS_ALLOW_ORIGINS`, `SECRET_KEY`,
`DATA_DIR`, `VIDEO_OUTPUT_DIR`, `STORAGE_PROVIDER` (`local` | `firebase`),
`MAX_REASONING_ITERATIONS` (adversarial loop bound), `MAX_HYPOTHESES` (candidate cap),
`JOB_POLL_INTERVAL_SECONDS`, `FIREBASE_*` — see `.env.example` for defaults and
comments on the remaining keys.

### Startup validation

`validate_settings()` + `validate_provider_types()` run at API startup
(`app/main.py` lifespan):

- **Development** (`APP_ENV != production`): problems are logged as warnings; the stack
  stays runnable on mocks.
- **Production**: any problem aborts startup. Required in production:
  - `SECRET_KEY` set to a unique value,
  - `CORS_ALLOW_ORIGINS` set explicitly, no wildcard,
  - Firebase auth configured (`FIREBASE_PROJECT_ID`, `FIREBASE_CLIENT_EMAIL`,
    `FIREBASE_PRIVATE_KEY`) — the built-in DEV user must not be used,
  - `DATABASE_URL` set,
  - and for every non-mock capability: a known provider type with the credentials that
    type requires (`http_chat` needs base URL, key and model).

BAKKE never silently falls back to a mock when live configuration is invalid: problems
are reported at startup (`ConfigError` aborts a production boot) and a misconfigured
adapter still raises if it is constructed (`ProviderConfigurationError`).

## Auth

Dev mode: when `APP_ENV != production` (the default), auth returns a clearly labelled
built-in DEV user (`dev@bakke.local`) and **no credentials are required**. In production,
configure `FIREBASE_*` and the API verifies Firebase ID tokens.

## Tests

```bash
# backend (no services or API keys needed)
cd apps/backend
DATABASE_URL="sqlite:///:memory:" ../../.venv/bin/python -m pytest tests/ -q
```

Four layers: `tests/unit`, `tests/contract`, `tests/integration`, `tests/e2e`
(see `docs/testing.md`).

```bash
# frontend
cd apps/frontend && npm run build && npm run lint
```
