# Architecture

## Purpose

BAKKE is an **Evidence-Constrained Hypothesis Intelligence** system. It never determines
*what happened*. Instead it:

1. Extracts facts from every evidence item.
2. Discovers constraints (temporal, spatial, presence, causation, physical).
3. Generates multiple scenarios (hypotheses) that are *compatible with* the evidence.
4. Eliminates scenarios that violate hard constraints, via an iterative adversarial
   review + expansion loop.
5. Ranks the survivors with an **Evidence Consistency Score** (consistency with available
   evidence — **not** probability).
6. Renders a labelled, visual-only **3D animated reconstruction** of a scenario.

Everything is auditable: every step is written to an `audit_events` trail.

## Layout

```
backend/
  app/
    main.py            # FastAPI app factory
    config.py          # Settings (pydantic-settings)
    database.py        # engine, session, get_db (commits on success)
    models/            # SQLAlchemy ORM models
    schemas/           # Pydantic request/response DTOs
    api/               # Routers (cases, scenarios) + auth dependency
    providers/         # Pluggable AI providers (registry + mocks + real)
    agents/            # Deterministic agents (contracts + orchestration)
    services/          # Case / analysis / scenario / video / audit services
    constraints/       # Constraint engine
    reasoning/         # Hypothesis gen, dedup, scoring, ranking
    retrieval/         # Analogical similar-case retrieval
    jobs/              # Background job queue + worker
    core/              # ids, hashing, storage
  frontend/
    app/               # Next.js App Router pages (dashboard, case, evidence,
                       #   timeline, scenarios, scenario detail, compare,
                       #   visualization, audit)
    components/        # QueryProvider, Nav, ui primitives, ScenarioCard
    lib/               # types.ts, api.ts (axios + streaming URL helper)
```

## Pipeline

`POST /api/cases/{case_id}/analyze` enqueues an `ANALYZE_CASE` job. The **worker**
(`backend/app/jobs/worker.py`) claims it and runs `AnalysisService.analyze_case`:

```
evidence ──extract──▶ facts + entities + findings
   │                       │
   └──retrieve────▶ similar cases (reference ONLY, never transferred as fact)
                          │
                          ▼
                    constraint engine ──▶ hard & soft constraints
                          │
                          ▼
                    hypothesis generation (dynamic count based on facts)
                          │
                          ▼
              iterative adversarial loop (≤ MAX_REASONING_ITERATIONS):
                  review scenario against constraints & facts
                  → HARD violation?  REJECT
                  → weak / unexplored?  REVISE / EXPAND, regenerate
                          │
                          ▼
         leftover validation (≤ MAX_LEFTOVER_VALIDATIONS candidates)
                     re-check the candidates the loop left unvalidated
                          │
                          ▼
                    scoring + ranking (survivors)
                          │
                          ▼
               build visual spec (director, visual-only)  ──▶ video job
```

`POST /api/cases/{id}/scenarios/{scenario_id}/visualize` enqueues a
`GENERATE_VIDEO` job. The worker builds the visual spec and renders the MP4.

## Agents

`backend/app/agents/contracts.py` defines typed drafts exchanged between the pipeline
and providers:

- `ExtractionResult` — facts, entities, findings, timeline from one evidence item.
- `HypothesisSet` / `HypothesisDraft` — scenario candidates with events.
- `CritiqueResult` / `RevisionResult` / `ExpansionResult` — adversarial loop outputs.

The deterministic agents (`extract.py`, `fusion.py`, `reasoning.py`, `director.py`)
orchestrate these contracts; providers (`llm.py`, `rule_based.py`, `schematic.py`)
implement them. The default `mock` implementations are pure-Python and deterministic so
the whole pipeline runs with no external API and produces reproducible results.

## Key design decisions

- **Evidence Consistency Score, never probability.** The score reflects how well a
  scenario is supported by the currently available evidence; it is not a claim about
  likelihood of truth.
- **Reference, not precedent.** Retrieved similar cases provide *patterns and ideas* for
  hypothesis generation. Their conclusions are never injected as facts.
- **Hard constraints eliminate; soft constraints weigh.** A hard-constraint violation
  rejects the scenario outright; soft constraints reduce its score.
- **Video is visual-only and labelled.** The director receives only the scenario's visual
  description (locations, objects, actors, timing), never case reports, evidence IDs, or
  forensic reasoning. Every video is labelled *NOT RECORDED FOOTAGE*.
- **Audit everything.** Extraction, fusion, constraint checks, adversarial iterations,
  scoring, ranking, and video generation are all recorded with agent, provider, and
  source object ids.
- **Pluggable providers with safe defaults.** The default configuration is 100% local and
  deterministic; switching to real providers requires explicit config and never leaks
  evidence to providers that aren't configured.
