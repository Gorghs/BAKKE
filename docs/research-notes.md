# Research Notes

## What BAKKE is

BAKKE is an **Evidence-Constrained Hypothesis Intelligence** system. Its stance is
deliberately anti-deterministic: it does not tell an investigator *what happened*. It
keeps every hypothesis that is compatible with the evidence, eliminates the ones that
aren't, and lets an analyst weigh the rest.

## Core principles

1. **Never determine what happened.** The output is a set of evidence-compatible
   scenarios, each with a score describing *consistency with currently available
   evidence* — never a probability and never a verdict.
2. **Elimination over affirmation.** Hard constraints (temporal, spatial, presence,
   causation, physical) eliminate scenarios. This mirrors forensic elimination reasoning
   and is the strongest claim the system makes.
3. **Adversarial iteration.** Every scenario is re-examined against the full constraint
   set and fact base; weak spots trigger revision/expansion rather than silent
   acceptance. This is where most of the "intelligence" lives.
4. **Analogy is reference, not precedent.** Similar historical cases contribute candidate
   *patterns* for hypothesis generation but their conclusions are never transferred as
   facts. This is a strict safety boundary.
5. **Visual reconstruction is cosmetic, not evidential.** The 3D video is an annotated
   visualization of the scenario's visual content, explicitly labelled not footage, and
   isolated from all reasoning/evidence detail so it can never be mistaken for a finding.
6. **Total auditability.** Every extraction, fusion, constraint check, review iteration,
   score, and render is recorded with its agent, provider, and source objects.

## Score meaning

The Evidence Consistency Score reflects how well the scenario accounts for the available
evidence (supported vs contradicted, anchor satisfaction, unknown periods, constraint
hardness). It is a *consistency* measure under current information, not a likelihood.
The UI and API docs both say so explicitly.

## Current implementation status

- Backend: extraction, fusion, constraints, anchors, conflicts, hypothesis generation,
  adversarial review/expansion, scoring, ranking, similar-case retrieval, video spec +
  mock renderer, audit, job queue (Redis wake-up + DB polling worker), Postgres via
  Alembic.
- Frontend: dashboard, case creation, evidence upload, timeline/conflicts/constraints,
  scenario list + detail (score breakdown, events, unknowns, video), compare,
  visualization player, audit trail.
- Providers: fully deterministic mocks by default (no API keys, nothing leaves the
  machine); OpenAI hooks exist for LLM/embeddings/STT/vision/video.

## Known limitations / next steps

- Mock LLM provider is rule-based; a real provider should be validated for hallucination
  and prompt-injection resistance (`ai-system-testing` guidance applies).
- Video renderer is schematic (shapes + labels); a photorealistic renderer would plug in
  behind the same visual-only spec.
- Multi-user isolation is dev-mode only; production auth (Firebase) is implemented but
  untested against real tokens.
- Constraint discovery currently relies on evidence text + explicit rules; adding
  constraint *elicitation* from analysts is a natural extension.
