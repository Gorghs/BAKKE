# AGENTS.md — BAKKE working guidelines

This file is for AI coding agents working in this repository. Read it before editing.

## Non-negotiables (product rules)

- BAKKE **never determines what happened**. Never add code that emits a verdict,
  "most likely cause", or probability. Scores are **Evidence Consistency Scores** only.
- **No fabrication.** An empty fact set or zero-survivor case must produce no
  hypotheses/scenarios. Similar-case retrieval is **reference-only** — its conclusions
  must never be injected as facts.
- The video **director** receives **visual-only** input: locations, objects, actors,
  timing, camera. Never pass case reports, evidence IDs, or forensic reasoning into the
  visual spec or renderer.
- Mock providers must be labelled (`is_mock: true`, "DEVELOPMENT MOCK"). No API keys are
  committed; evidence is never sent to a provider that isn't explicitly configured.

## Conventions

- Python 3.12+ (docker) / 3.14 (local venv at `../../.venv` from `apps/backend/`).
- `metadata` is **not** a valid column name (SQLAlchemy reserved). Pydantic draft objects
  use `.metadata`; ORM models use `.extra` (JSON).
- Fact/Finding/Timeline rows need an explicit `db.flush()` after insert so surrogate IDs
  are stable (they feed audit `source_object_ids` and fusion references).
- API writes are committed by `get_db` (`apps/backend/app/database.py`) — services should
  `db.flush()`, not `db.commit()`. The worker (`app/infrastructure/jobs/worker.py`) commits its own
  session after each job.
- Provider code belongs in `app/adapters/` behind the protocols in `app/ports/`. The
  adapter catalogue (`app/adapters/providers/`) is the only place mapping a
  `provider_type` to a class; core/domain code never hardcodes vendor or model names.
- Prompts live in `app/prompts/v1/` (`PROMPT_VERSION` in `app/prompts/__init__.py`);
  the version is recorded in audit entries and replay manifests. New LLM task = add a
  prompt file + `LLM_TASKS` / `TASK_SCHEMAS` entries — both mock and live providers
  validate output against the schema.
- Jobs are thin dispatch: `app/infrastructure/jobs/tasks.py` `HANDLERS` maps a job type
  to exactly one workflow in `app/workflows/`.

## Commands

```bash
# tests (58: unit/contract/integration/e2e, no services needed)
cd apps/backend && DATABASE_URL="sqlite:///:memory:" ../../.venv/bin/python -m pytest tests/ -q

# run API + worker locally
cd apps/backend && ../../.venv/bin/uvicorn app.main:app --port 8000
cd apps/backend && ../../.venv/bin/python -m app.infrastructure.jobs.worker

# migrations
cd apps/backend && ../../.venv/bin/alembic upgrade head

# full stack
docker compose up --build            # postgres :5432, redis :6380, api :8000, web :3000

# seed demo
docker compose exec backend python -m scripts.seed_demo

# frontend build check
cd apps/frontend && npm run build
```

## Smoke flow to re-verify the stack

1. `docker compose up -d` → `/health` ok, `/api/providers` shows mocks.
2. Create case → upload ≥7 right-hip PM reports + FR + IR → `POST /api/cases/{id}/analyze`.
3. Poll `/api/cases/{id}/analysis/status` until `SUCCEEDED`; open the case in the
   frontend (`/cases/{id}`) — `/api/cases/{id}/dashboard` shows ≥1 survivor.
4. `POST /api/cases/{id}/scenarios/{sid}/visualize` → poll
   `/api/cases/{id}/scenarios/{sid}/video` until `READY`; stream
   `/api/videos/{vid}/stream` (expect 206 on Range).
5. Check the audit trail (`GET /api/cases/{id}/audit`) for fusion,
   hypothesis/scoring, constraint rejections (`scenario_rejection`),
   `adversarial_review` and `video_generated` entries.
