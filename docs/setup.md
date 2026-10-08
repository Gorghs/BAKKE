# Setup

## Prerequisites

- Docker + Docker Compose (recommended) **or** Python 3.12+ / Node 20+ run locally.
- ffmpeg/ffprobe on PATH for local video generation (`apt install ffmpeg` or Homebrew).
- Optional: `OPENAI_API_KEY` for real LLM/embedding/vision/STT providers.

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

The backend runs `alembic upgrade head` on startup, so the schema is created automatically.

Seed the demo case (7 evidence items that pass/right-hip vs chest + video):

```bash
docker compose exec backend python -m scripts.seed_demo
```

Without Docker:

```bash
cd apps/backend
python -m venv ../../.venv && ../../.venv/bin/pip install -r requirements.txt
cp ../.env.example ../.env
# run migration, API and worker in three shells
../../.venv/bin/alembic upgrade head
../../.venv/bin/uvicorn app.main:app --port 8000
../../.venv/bin/python -m app.infrastructure.jobs.worker
```

Frontend (local):

```bash
cd apps/frontend
npm install
npm run dev            # http://localhost:3000
```

## Configuration

All settings come from the `.env` file (see `apps/backend/app/config.py`). The important ones:

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./data/bakke.db` | SQLAlchemy URL; use the Postgres URL in compose |
| `REDIS_URL` | `redis://localhost:6379/0` | Worker wake-up pub/sub (falls back to polling) |
| `LLM_PROVIDER` | `mock` | `mock`, `openai`, or `anthropic` |
| `EMBEDDING_PROVIDER` | `mock` | `mock` or `openai` |
| `STT_PROVIDER` | `mock` | `mock` or `openai` |
| `VISION_PROVIDER` | `mock` | `mock` or `openai` |
| `VIDEO_UNDERSTANDING_PROVIDER` | `mock` | `mock` or `openai` |
| `VIDEO_GENERATION_PROVIDER` | `mock` | `mock` or `openai` |
| `OPENAI_API_KEY` | (empty) | Real provider key; only required when providers are switched off `mock` |
| `MAX_REASONING_ITERATIONS` | `5` | Adversarial review/expand iterations |
| `MAX_HYPOTHESES` | `60` | Cap on hypothesis scenarios |
| `TOP_N_DEFAULT` | `10` | Default number of scenarios ranked |
| `JOB_POLL_INTERVAL_SECONDS` | `1.0` | Worker polling interval |

Dev mode: when `APP_ENV != production` (the default), auth returns a clearly labelled
built-in DEV user (`dev@bakke.local`) and **no credentials are required**. In production,
configure `FIREBASE_*` and the API will verify Firebase ID tokens.

## Providers

All AI providers are pluggable through `apps/backend/app/infrastructure/providers/registry.py`. The
`mock` implementations are deterministic and clearly marked **DEVELOPMENT MOCK** in every
API response (`is_mock: true`). Evidence is never sent to any provider that is not
explicitly configured; in the default configuration nothing leaves the machine.
