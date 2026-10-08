# API

Base URL: `http://localhost:8000/api` (dev mode: no auth required — the API uses the
built-in DEV user. Production requires a Firebase `Authorization: Bearer <id-token>`).

Interactive docs: http://localhost:8000/docs

## Cases

| Method | Path | Description |
|---|---|---|
| `GET` | `/cases` | List the current user's cases |
| `POST` | `/cases` | Create a case `{name, description?, tags?}` |
| `GET` | `/cases/{id}` | Case detail |
| `PATCH` | `/cases/{id}` | Update name / description / tags |
| `GET` | `/cases/{id}/dashboard` | Aggregated dashboard stats + top scenarios |
| `GET` | `/cases/{id}/audit` | Audit trail for the case |

## Evidence

| Method | Path | Description |
|---|---|---|
| `POST` | `/cases/{id}/evidence` | Upload evidence (multipart: `item_type`, `title`, `description`, `raw_text`, optional `file`) |
| `GET` | `/cases/{id}/evidence` | List evidence |
| `GET` | `/cases/{id}/facts` | Extracted facts |
| `GET` | `/cases/{id}/facts/{fact_id}` | One fact with its source evidence |
| `GET` | `/cases/{id}/entities` | Extracted entities |
| `GET` | `/cases/{id}/graph` | Entity nodes + relationship edges |
| `GET` | `/cases/{id}/findings` | Extracted findings |
| `GET` | `/cases/{id}/timeline` | Fused timeline events |
| `GET` | `/cases/{id}/conflicts` | Detected conflicts |
| `GET` | `/cases/{id}/constraints` | Discovered constraints |
| `GET` | `/cases/{id}/anchors` | Forensic anchors (firm, accepted evidence) |
| `GET` | `/cases/{id}/similar-cases` | Retrieved similar cases (reference only) |

`item_type` values (`EVIDENCE_TYPES`, `app/domain/constants.py`): `TEXT`, `AUDIO`,
`IMAGE`, `VIDEO`, `FORENSIC_REPORT`, `POST_MORTEM_REPORT`, `INVESTIGATOR_REPORT`,
`WITNESS_STATEMENT`, `PHYSICAL_EVIDENCE`, `LOCATION_RECORD`, `DIGITAL_RECORD`, `OTHER`.
Text types may use `raw_text`; `AUDIO`, `IMAGE`, `VIDEO` and `PHYSICAL_EVIDENCE` need a
file (or `raw_text`), and an empty file is rejected.

## Analysis

| Method | Path | Description |
|---|---|---|
| `POST` | `/cases/{id}/analyze` | Enqueue full analysis (returns `job_id`) |
| `GET` | `/cases/{id}/analysis/status` | Job status + progress + result |

## Scenarios

| Method | Path | Description |
|---|---|---|
| `GET` | `/cases/{id}/scenarios` | All scenarios (flat list with score, status, survivor flag) |
| `GET` | `/cases/{id}/scenarios/{sid}` | Scenario detail: score breakdown, events, known / inferred / unknown lists, satisfied anchors, similar cases, discriminating evidence, video, audit slice |
| `POST` | `/cases/{id}/scenarios/{sid}/validate` | Re-run constraint validation for the scenario |
| `POST` | `/cases/{id}/scenarios/{sid}/visualize` | Enqueue video generation job |
| `GET` | `/cases/{id}/scenarios/{sid}/spec` | Visual-only spec + shot list |
| `POST` | `/scenarios/compare` | Compare 2-4 scenarios: shared/differing evidence, discriminating evidence |
| `GET` | `/scenarios/{sid}/video` | Video metadata for a scenario |

## Video streaming

| Method | Path | Description |
|---|---|---|
| `GET` | `/videos/{vid}/stream` | MP4 stream (supports `Range` headers) |

## Providers

| Method | Path | Description |
|---|---|---|
| `GET` | `/providers` | Per-capability provider report: adapter id, model, base URL, `is_mock`, resolution source; runtime `configured_keys` and masked secrets |
| `PUT` | `/providers` | Store runtime overrides in the DB (applies without a restart); unknown provider types are rejected with 422 |

Generic keys (`LLM_PROVIDER_TYPE`, `LLM_API_KEY`, …) are preferred; legacy names are
accepted. Secrets are never returned unmasked.

## Replay

| Method | Path | Description |
|---|---|---|
| `POST` | `/cases/{id}/replay` | Re-run a workflow offline. Body `{job_type: "ANALYZE_CASE" \| "GENERATE_VIDEO", scenario_id?}`; all providers forced to mock; returns the replay result plus `original_manifest` |
| `GET` | `/cases/{id}/replay/manifest?kind=analysis` | Recorded replay manifest (`video_{scenario_id}` for a video run) |

Every response that can be produced by a mock includes `is_mock: true` so callers can
display the **DEVELOPMENT MOCK** badge.

## System

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Health + database connectivity |
