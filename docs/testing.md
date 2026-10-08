# Testing

## Running the suite

```bash
cd apps/backend
DATABASE_URL="sqlite:///:memory:" ../../.venv/bin/python -m pytest tests/ -q
```

Tests use SQLite engines created in `tests/conftest.py` (per-test temp file, plus the
in-memory `DATABASE_URL`); no external services, Docker or API keys are required.
Provider env is forced to explicit mocks by `conftest.py` before any app module reads
settings.

Frontend checks:

```bash
cd apps/frontend && npm run build && npm run lint
```

## Layers

| Layer | Directory | What it covers |
|---|---|---|
| unit | `tests/unit` | `test_config` — capability defaults are explicit mock, legacy `openai` → `http_chat`, generic beats legacy, runtime DB override wins, `validate_settings` (incl. production strictness); `test_domain_and_prompts` — every task has a versioned prompt, typed tasks embed a JSON schema, bad output fails loudly, `domain/` stays ORM/adapter-free; domain rules: `test_forensic_rule`, `test_iterative_reasoning`, `test_dynamic_hypotheses`, `test_similar_cases`, `test_compare_scenarios` |
| contract | `tests/contract` | `test_provider_ports` — mock and `http_chat` adapters satisfy their ports, schema violations are rejected, unknown provider types and missing credentials fail clearly, catalogue + `validate_provider_types` (HTTP calls go through a mocked transport) |
| integration | `tests/integration` | `test_demo_pipeline` — demo data through the whole AnalyzeCase workflow (7 evidence items extracted, survivors kept, hard rejection recorded, similar cases retrieved; no evidence ⇒ no scenarios); `test_video_isolation`; `test_zero_scenario` |
| e2e | `tests/e2e` | `test_api_flow` — health, capability discovery shape, provider PUT validation and key masking, analysis flow, compare endpoint; `test_replay` — offline replay keeps the original manifest intact and writes a replay sidecar |

## What the tests assert about the product rules

- **No fabrication**: an empty fact set yields zero hypotheses; zero survivors yield no
  output.
- **Elimination by constraint**: hard violations (e.g. injury location mismatch) reject a
  scenario with an explicit reason.
- **Adversarial review works**: temporal and spatial inconsistencies between anchors and
  scenario events are caught.
- **Similar cases inform, never decide**: their content appears only as reference labels
  and patterns.
- **Video isolation**: the director's spec contains only visual information.
- **Explicit configuration**: capabilities default to labelled mocks; a live type without
  credentials fails loudly instead of degrading.

## Manual end-to-end smoke

1. `docker compose up --build`
2. `docker compose exec backend python -m scripts.seed_demo`
3. `POST /api/cases/{id}/analyze` → poll `GET /api/cases/{id}/analysis/status` until
   `SUCCEEDED`
4. `POST /api/cases/{id}/scenarios/{sid}/visualize` → poll
   `GET /api/scenarios/{sid}/video` until `READY`
5. Stream `GET /api/videos/{vid}/stream` (Range requests → 206)
6. `GET /api/cases/{id}/audit` for the recorded trail, and
   `POST /api/cases/{id}/replay` for an offline re-run (all providers forced to mock)
7. Browse http://localhost:3000, open the case, walk Evidence → Timeline → Scenarios →
   scenario detail → Compare → Visualization → Audit.
