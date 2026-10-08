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
| `GET` | `/cases/{id}/entities` | Extracted entities |
| `GET` | `/cases/{id}/findings` | Extracted findings |
| `GET` | `/cases/{id}/timeline` | Fused timeline events |
| `GET` | `/cases/{id}/relationships` | Entity relationships |
| `GET` | `/cases/{id}/conflicts` | Detected conflicts |
| `GET` | `/cases/{id}/constraints` | Discovered constraints |
| `GET` | `/cases/{id}/anchors` | Forensic anchors (firm, accepted evidence) |

`item_type` values: `POST_MORTEM_REPORT`, `FORENSIC_REPORT`, `INVESTIGATOR_REPORT`,
`TESTIMONY`, `AUDIO`, `IMAGE`, `VIDEO`, `PHYSICAL_EVIDENCE`. Text types may use
`raw_text`; media types require a file upload.

## Analysis

| Method | Path | Description |
|---|---|---|
| `POST` | `/cases/{id}/analyze` | Enqueue full analysis (returns `job_id`) |
| `GET` | `/cases/{id}/analysis/status` | Job status + progress + result |

## Scenarios

| Method | Path | Description |
|---|---|---|
| `GET` | `/cases/{id}/scenarios` | All scenarios (flat list with score, status, survivor flag) |
| `GET` | `/cases/{id}/scenarios/{sid}` | Scenario detail: score breakdown, events, unknowns, similar cases, anchors, video |
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
| `GET` | `/providers` | Active provider registry, mock flags, labels |

Every response that can be produced by a mock includes `is_mock: true` so callers can
display the **DEVELOPMENT MOCK** badge.

## System

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Health + database connectivity |
