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
apps/frontend/    Next.js 14 (App Router) + TypeScript + Tailwind + TanStack Query
docs/             documentation (architecture, api, database, setup, testing, ...)
scripts/          repo-level launchers (seed_demo)
data/             runtime uploads / videos (gitignored, docker volume)
docker-compose.yml
```

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

## Tests

```bash
cd apps/backend && DATABASE_URL="sqlite:///:memory:" ../../.venv/bin/python -m pytest tests/ -q
```

23 tests, no services or API keys needed. See `docs/testing.md`.

## Documentation

- `docs/architecture.md` — pipeline, agents, key design decisions
- `docs/api.md` — endpoint reference
- `docs/database.md` — schema, migrations, conventions
- `docs/video-pipeline.md` — visual-only spec + renderer isolation
- `docs/research-notes.md` — principles, score semantics, limitations
- `docs/setup.md` — full configuration reference
- `AGENTS.md` — working guidelines for AI agents editing this repo