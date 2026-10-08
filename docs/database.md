# Database

## Engine

SQLAlchemy 2.0, Alembic migrations. Default dev database is SQLite
(`data/bakke.db`); docker-compose uses PostgreSQL 16 (`postgresql+psycopg2://bakke:bakke@postgres:5432/bakke`).

## Migrations

```bash
cd apps/backend
../../.venv/bin/alembic upgrade head     # apply
../../.venv/bin/alembic revision --autogenerate -m "describe change"   # new migration
```

Migrations live in `apps/backend/alembic/versions/`:

- `5a69a0d5ecc5_init.py` — the initial schema (verified against Postgres).
- `a1b2c3d4e5f6_add_provider_settings.py` — `provider_settings`, the runtime
  provider-override table behind `PUT /api/providers`.

The dockerized backend and worker both run `alembic upgrade head` before starting.

## Model groups

All models inherit `app/models/base.py` (id = string UUID, created_at/updated_at).

| Group | Models |
|---|---|
| Users & cases | `User`, `Case` |
| Evidence | `EvidenceItem` (case-linked, `evidence_id` like `E-001`, content hash, status), `EvidenceSource`, per-type asset tables (`DocumentAsset`, `AudioAsset`, `ImageAsset`, `VideoAsset`) |
| Fusion | `Fact` (`extra` JSON: source ids, certainty, injury location, camera coverage, etc.), `Entity` (+ `Person` / `Object` / `Location` / `Event` subtypes), `EntityRelationship`, `Finding` |
| Timeline | `TimelineEvent` (ordering index, time window, location) |
| Constraints | `Constraint` (HARD/SOFT, type), `Conflict` (two constraints/anchors in tension), `ForensicAnchor` (firm evidence, timestamps) |
| Hypotheses & scenarios | `Hypothesis` (e.g. `H-012`), `Scenario` (summary, cause claim, status, survivor, rejection reason, `extra` rank), `ScenarioEvent`, `ScenarioScore` (total + breakdown JSON), `ScenarioEvidenceLink` (supporting / contradicting), `DiscriminatingEvidence`, `ScenarioComparison` |
| Similar cases | `ReferenceCase` (embedded reference corpus), `SimilarCase` (reference label, similarity, relevant patterns; reference-only) |
| Video | `VideoScenarioSpec` (visual-only prompt + `spec` JSON: characters, objects, unknown regions, duration), `VideoShot` (index, duration, description, prompt fragment), `GeneratedVideo` (status, provider, spec_id, dimensions, duration, validation JSON, label, `is_mock`) |
| Audit | `AuditEvent` (action, agent, provider, summary, source object ids, `prompt_version`; `extra` JSON carries `run_id` and stage counts), `Job` (status, progress, result, error, attempts) |
| Runtime config | `ProviderSetting` (key/value rows for generic + legacy provider keys; highest-resolution source for capability config) |

## JSON conventions

- `extra` (JSON column) holds structured enrichment: e.g. `Fact.extra =
  {"evidence_type", "camera_coverage": "NO_COVERAGE", "injury_location"}`,
  `Scenario.extra = {"rank": n}`.
- SQLAlchemy's reserved `metadata` name is avoided; Pydantic draft objects use
  `.metadata` and ORM models use `.extra`.

## Notes

- SQLite uses `check_same_thread=False` and enables foreign keys per-connection.
- `get_db` (FastAPI dependency) **commits on success** and rolls back on error — API
  writes are transactional. The worker session commits after each job.
- `scripts/seed_demo.py` seeds the demo case deterministically (right-hip passing set +
  a chest-injury variant that must be rejected, plus a video).
