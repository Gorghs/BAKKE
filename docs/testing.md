# Testing

## Running the suite

```bash
cd apps/backend
DATABASE_URL="sqlite:///:memory:" ../../.venv/bin/python -m pytest tests/ -q
```

23 tests, green in ~2s. Tests use an in-memory SQLite engine created in
`tests/conftest.py`; no external services or API keys required.

## Coverage areas

| File | Coverage |
|---|---|
| `test_demo_pipeline.py` | Full `seed_demo` pipeline: 7 evidence items → 27 hypotheses → 13 survivors, 1 hard rejection, 3 similar cases, video ready |
| `test_dynamic_hypotheses.py` | Hypothesis count scales with fact complexity (2 / 7 / 17); chest-injury candidate is generated and rejected |
| `test_forensic_rule.py` | Right-hip scenario passes, chest scenario rejected with HARD FORENSIC CONFLICT vs FA-001 |
| `test_iterative_reasoning.py` | Temporal conflict (Hallway 20:14 vs Building 20:10) and spatial conflict are detected; iterations recorded; similar cases are reference-only |
| `test_similar_cases.py` | Similar-case patterns influence generation but conclusions never become facts |
| `test_video_isolation.py` | Video prompt is visual-only: no evidence IDs (E-00x), no case reports, no forensic reasoning leakage |
| `test_compare_scenarios.py` | Compare surfaces shared supporting evidence, scenario-specific evidence, participant/cause differences, and never emits probability language |
| `test_zero_scenario.py` | Zero survivors ⇒ no fabricated scenarios returned |

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

## Manual end-to-end smoke

1. `docker compose up --build`
2. `docker compose exec backend python -m scripts.seed_demo`
3. `POST /api/cases/{id}/analyze` → poll `/analysis/status` until `SUCCEEDED`
4. `POST /api/cases/{id}/scenarios/{sid}/visualize` → poll `GET /api/scenarios/{sid}/video`
   until `READY`
5. Stream `GET /api/videos/{vid}/stream` (Range requests → 206)
6. Browse http://localhost:3000, open the case, walk Evidence → Timeline → Scenarios →
   scenario detail → Compare → Visualization → Audit.
