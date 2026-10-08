# BAKKE — Evidence-Constrained Hypothesis Intelligence

BAKKE explores every hypothesis that is *compatible with the evidence*, eliminates the
ones that violate hard constraints via adversarial review, ranks the survivors by an
**Evidence Consistency Score** (never a probability), and renders a labelled, visual-only
3D animated reconstruction of a scenario.

> BAKKE never determines what happened. It presents the evidence-compatible possibilities
> and eliminates what the evidence rules out.

## Stack

```
apps/backend/     FastAPI + SQLAlchemy 2.0 + Alembic + background worker (Redis/DB)
  app/ports/      provider-agnostic protocols (llm, embeddings, speech, vision, video, storage, repos)
  app/adapters/   http_chat + mock + vendor video adapters, persistence, storage
  app/prompts/    versioned prompts (v1) + typed task output schemas
  app/workflows/  AnalyzeCase / GenerateVideo / offline replay (manifests in data/replay/)
  data/           runtime uploads / videos / replay manifests (gitignored, docker volume)
  tests/          unit / contract / integration / e2e
apps/frontend/    Next.js 14 (App Router) + TypeScript + Tailwind + TanStack Query
docs/             documentation (architecture, api, database, setup, testing, ...)
scripts/          repo-level launchers (seed_demo)
docker-compose.yml   Makefile   pyproject.toml
```

Provider-agnostic by construction: workflows and domain code depend on the ports in
`app/ports/`, concrete providers are selected at runtime through the adapter catalogue
(`app/adapters/providers/`), and background jobs (`app/infrastructure/jobs/`) are thin
dispatch over `app/workflows/`.

## Quick start (Docker)

```bash
cp .env.example .env
docker compose up --build
# API       -> http://localhost:8000/docs
# Frontend  -> http://localhost:3000
# Postgres  -> localhost:5432 (bakke/bakke)
# Redis     -> localhost:6380 (host 6379 remapped; may be taken by other tools)
```

The backend and worker run `alembic upgrade head` automatically. Dev mode uses a
built-in, clearly-labelled DEV user — no credentials needed.

Seed the demo case (pass/right-hip set + chest variant that must be rejected + a video):

```bash
docker compose exec backend python -m scripts.seed_demo
```

Then trigger the pipeline and open the frontend:

```
POST /api/cases/{id}/analyze        # runs on the worker
# open http://localhost:3000 → open the case → Scenarios → Visualization
```

## Run locally

```bash
# backend (Python 3.12+)
cd apps/backend
python -m venv ../../.venv && ../../.venv/bin/pip install -r requirements.txt
../../.venv/bin/alembic upgrade head
../../.venv/bin/uvicorn app.main:app --port 8000     # API
../../.venv/bin/python -m app.infrastructure.jobs.worker            # worker (second shell)

# frontend (Node 20+)
cd apps/frontend
npm install
npm run dev
```

## Provider configuration

Every AI capability (text, embeddings, speech, vision, video understanding,
video generation) uses the same four keys — see `.env.example`:

```bash
<PREFIX>_PROVIDER_TYPE     # unset (default: mock) | mock | http_chat | <vendor adapter id>
<PREFIX>_API_BASE_URL      # base URL of the provider's HTTP API
<PREFIX>_API_KEY           # API key / bearer token
<PREFIX>_MODEL             # model identifier
```

Prefixes: `LLM_`, `EMBEDDING_`, `STT_`, `VISION_`, `VIDEO_UNDERSTANDING_`,
`VIDEO_GENERATION_`.

- Mock by default: with nothing configured, every capability runs a local
  provider labelled "DEVELOPMENT MOCK". Evidence only reaches a live provider
  when it is explicitly configured — invalid live configuration fails loudly
  and never falls back to mocks (production refuses to start).
- Legacy names (`OPENAI_API_KEY`, `LLM_PROVIDER`, ...) are still honoured when
  the generic key is unset.
- `GET` / `PUT` `/api/providers` reads and overrides this configuration at
  runtime (stored in the database; keys are returned only masked).

## Tests

```bash
cd apps/backend && DATABASE_URL="sqlite:///:memory:" ../../.venv/bin/python -m pytest tests/ -q
```

58 tests (unit / contract / integration / e2e), no services or API keys needed. See `docs/testing.md`.

## Documentation

- `docs/architecture.md` — pipeline, agents, key design decisions
- `docs/api.md` — endpoint reference
- `docs/database.md` — schema, migrations, conventions
- `docs/video-pipeline.md` — visual-only spec + renderer isolation
- `docs/research-notes.md` — principles, score semantics, limitations
- `docs/setup.md` — full configuration reference
- `AGENTS.md` — working guidelines for AI agents editing this repo