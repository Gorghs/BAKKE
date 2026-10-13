# AGENTS.md: BAKKE working guidelines

For AI agents editing this repository. Read this before changing code.

## Product rules

Enforced by tests and by the rest of the docs. Code that breaks them is a bug even
when it runs.

- BAKKE never decides what happened. No verdicts, no "most likely cause", no
  probabilities. Scores are Evidence Consistency Scores only.
- No fabrication. An empty fact set or a zero-survivor case produces zero
  hypotheses and zero scenarios. Similar-case retrieval is reference only; its
  conclusions never become facts.
- The video director takes visual input only: locations, objects, actors, timing,
  camera. Case reports, evidence IDs and forensic reasoning stay out of the visual
  spec and the prompt (`app/agents/director.py`, asserted by
  `tests/test_video_isolation.py`).
- Mock providers carry `is_mock: true` and the label "DEVELOPMENT MOCK". No API
  keys in the repo. Evidence goes only to providers that were configured
  explicitly.

## Commands

The virtualenv lives at `../.venv`, one level above the repo rather than inside it.
The README, the Makefile and every command below assume that path. Build it on
Python 3.12+ (`pyproject.toml` allows 3.11 and up, the Docker image runs 3.12).

```bash
# tests: 71 items, ~13s, no services and no API keys
cd backend && DATABASE_URL="sqlite:///:memory:" ../.venv/bin/python -m pytest
cd backend && ../.venv/bin/python -m pytest tests/test_forensic_rule.py   # one file
cd backend && ../.venv/bin/python -m pytest -k zero_scenario              # one test

# API and worker: two shells, both started from backend/
cd backend && ../.venv/bin/uvicorn app.main:app --reload --port 8000
cd backend && ../.venv/bin/python -m app.jobs.worker

# migrations
cd backend && ../.venv/bin/alembic upgrade head

# every make target fails without .env (the Makefile does `include .env`)
cp .env.example .env && make api     # also: worker test seed migrate logs

# frontend, Node 20+
cd frontend && npm install && npm run build && npm run lint

# full stack: api :8000, web :3000, postgres :5432, redis :6380 on the host
docker compose up --build
docker compose exec backend python -m scripts.seed_demo
```

No linter or formatter is configured for the backend and there are no CI
workflows. `npm run build` and `npm run lint` are the only automated checks.

## State of the suite

All 71 tests pass on a clean checkout. The old isolation conflict is resolved:
`build_visual_spec` no longer puts `locations` or `injury_region` in the spec, so
neither key can reach the prompt. Keep it that way — `test_video_isolation.py` is
the guard. Forensic anchors are still passed to the director for conflict
checking, but their content must never be stored in the spec or written into a
prompt.

## Backend conventions

- `metadata` is reserved by SQLAlchemy. Pydantic drafts use `.metadata`, the ORM
  columns are named `extra` (JSON).
- Services call `db.flush()`, never `db.commit()`. `get_db`
  (`app/database.py`) commits at the end of the request, the worker commits its
  own session after each job, and sessions run with `autoflush=False`, so
  surrogate IDs stay unstable until an explicit flush.
- Adding an LLM task takes two edits: register the name in `LLM_TASKS`
  (`app/providers/base.py`) and add the matching `mock_<task>` function in
  `app/providers/rule_based.py`. `MockLLMProvider.run_task` builds that name and
  looks it up.
- Provider choice resolves per call in `app/providers/registry.py`: database
  override (`PUT /api/providers`) then environment then default, and a missing
  API key forces the mock regardless of the provider name.

## Runtime gotchas

- The migrations hardcode `server_default=sa.text('now()')`, which is Postgres
  only. On SQLite, `alembic upgrade head` creates tables whose inserts then fail
  with `unknown function: now()`, including the DEV user that `/api/me` and
  `/api/providers` insert on first use. For local SQLite, skip alembic and let
  `init_db()` in the seed scripts create the schema, or run against the Postgres
  from docker compose. The tests are unaffected because `tests/conftest.py`
  builds its schema with `create_all`.
- Settings read `.env` from the process working directory. Runs started in
  `backend/` read `backend/.env` and ignore the root `.env`; docker compose and
  the Makefile read the root one.
- The frontend takes its API base from `NEXT_PUBLIC_API_URL`, defined with its
  fallback in `frontend/lib/types.ts` (`http://localhost:8000/api`). There is no
  dev proxy or rewrite in `next.config.mjs`, so the URL must be reachable from
  the browser.
- Jobs are database rows (`ANALYZE_CASE`, `GENERATE_VIDEO`) and the worker polls
  them. `POST .../analyze` and `POST .../visualize` only enqueue, so nothing
  happens without a running worker. Redis only carries a best-effort wake-up
  message and publish failures are ignored, so it is not a requirement.
- Between jobs, the worker runs `app/jobs/supervisor.py` every 60s: it requeues
  FAILED jobs under the same 3-attempt cap as `claim_next_job`, requeues (or at
  the cap, fails) RUNNING rows older than 15 minutes, and writes one
  `job_queue_stalled` AuditEvent per stall for PENDING rows older than 5
  minutes. Changes show up in `GET /api/cases/{id}/audit`.
- Mock video rendering shells out to `ffmpeg`, installed in `backend/Dockerfile`.
  Install it locally before the video step.
- `scripts/seed_demo.py` runs analysis and video generation in-process, so it
  works without a worker, but each run adds another demo case. The reference
  library skips reseeding unless forced.

## Smoke flow

1. `docker compose up -d` → `GET /health` ok, `GET /api/providers` reports mocks.
2. `docker compose exec backend python -m scripts.seed_demo`, or create a case,
   `POST /api/cases/{id}/evidence` with multipart `item_type` / `raw_text`, then
   `POST /api/cases/{id}/analyze`.
3. Poll `GET /api/cases/{id}/analysis/status` until `SUCCEEDED`, then open
   `GET /api/cases/{id}/dashboard` for the survivors.
4. `POST /api/cases/{id}/scenarios/{sid}/visualize` → poll
   `GET /api/scenarios/{sid}/video` until `READY` → `GET /api/videos/{vid}/stream`
   (Range requests answer 206).
5. `GET /api/cases/{id}/audit` should list extraction, fusion, constraints,
   review and video entries.
