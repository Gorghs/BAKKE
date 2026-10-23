# Video Pipeline

## Goal

Produce a **labelled 3D animated reconstruction** of a surviving scenario. The video is
explicitly **not recorded footage** and must never leak the case's forensic reasoning.

## Isolation contract

- The **director** (`app/agents/director.py`) receives only the scenario's visual content:
  locations, objects, actors, timing windows, and camera descriptors. Forensic anchors are
  passed in for conflict checking only; their content never reaches the spec or the prompt.
- It never receives case reports, evidence IDs, fact sources, or reasoning text.
- The spec (`VideoScenarioSpec`) stores a JSON `spec` object plus a single `visual_prompt`
  string. The JSON holds `visual_prompt` (sent to the provider), `visual_prompt_director`
  (raw director output), `visual_brief` (provider, is_mock, used, reason) and a JSON `shots`
  list (each shot: index, duration, description, framing, direction, clock, start_seconds,
  end_seconds). `props`, `beats`, `continuity` and `absences` say what the clip must show and
  what it must never show; `unshown` lists what the caps left out, for the operator, and is
  never written into the prompt. No `injury_region` or top-level `locations` keys —
  `test_video_isolation.py` asserts the spec contains no `E-00x` evidence ids, no report
  excerpts, and no forensic reasoning.
- Every render is labelled `NOT RECORDED FOOTAGE`.

## Visual brief

`build_visual_spec` builds the brief the director works from, in
`app/agents/visual_brief.py`:

- The deterministic extractor reduces the scenario to setting, actors (stylised dummy
  figures), props with a start and end state, ordered beats, continuity rules and absences.
  An action needs a named actor, so a beat with none is reported in `unshown` rather than
  animated as a self-moving prop.
- With `VIDEO_VISUAL_BRIEF` on, the LLM task `build_visual_brief` may fill the same shape.
  A model brief is used only if every label, action word and clock already appears in the
  scenario text. Any violation rejects the brief whole and the deterministic one is used.
  A passing brief is merged with the deterministic one, so the model can never drop a stated
  action, object or absence. Continuity always comes from the deterministic brief, because a
  model line there would add a rule the scenario never implies.
- Absence events ("no vehicle entered") become continuity plus a constraint exclusion, never
  a shot. A state change becomes an explicit end-state shot that names the count ("exactly one
  padlock, no padlock appears after that").
- Shot timing follows from the beats: one establishing shot, one shot per beat with the tail
  folded so the clip never exceeds `MAX_SHOTS`, then the end state. The whole clip is
  `TARGET_TOTAL_SECONDS`, and a beat without its own clock inherits the one before it, so a
  removal that takes seconds is never stamped with an eleven-hour window.

## Prompt expansion

Off by default (`VIDEO_PROMPT_EXPANSION=false`). Left on, `build_spec` runs the director
prompt through `expand_visual_prompt` (`app/services/video_service.py`):

- One LLM task, `expand_video_prompt` (`LLM_TASKS`), aimed at prompt-to-video models.
- The expansion sees only the director prompt. It must keep the `NOT RECORDED FOOTAGE`
  label and must not add evidence IDs or forensic content; `_expansion_problem()` checks
  both, and any violation or provider error falls back to the raw director prompt
  (`prompt_expansion.fallback_reason` records why).
- The provider is chosen per call: database override, then environment. `OPENAI_BASE_URL`
  routes it to an OpenAI-compatible endpoint (Groq, DeepSeek, OpenRouter, Gemini); with no
  key or no base URL the mock returns the prompt unchanged.

## Renderer

`app/providers/schematic.py` (mock) renders with ffmpeg:

- Resolution **640×360**, **12 fps**, deterministic seeded colors/shapes per actor.
- Mock duration is **capped at 12 seconds** (`duration = min(duration, 12.0)`); the
  pipeline scales shots to fit.
- Shot construction: clear frame, draw shapes moving per timing windows, overlay location
  + timecode + `NOT RECORDED FOOTAGE` label, crossfade between shots.
- Validation caps the expected duration to the same bound.

## Data flow

```
surviving scenario
   └─▶ jobs/tasks.py GENERATE_VIDEO
        ├─ create GeneratedVideo(status=PENDING)   # spec_id nullable until built
        ├─ VideoService.build_spec(scenario)
        │    ├─ derive/receive visual brief    ──▶ setting, actors, props, beats, absences
        │    ├─ build_visual_spec + director   ──▶ raw visual prompt (visual-only)
        │    └─ expand_visual_prompt           ──▶ optional rewrite, off by default
        ├─ video.spec_id = spec.id
        └─ VideoService.generate_video(...)   ──▶ MP4 on disk + status READY
```

The video record stores provider, model, width/height, format, duration, size, label and
a `is_mock` flag. The API streams it via `GET /api/videos/{vid}/stream` with Range
support. The frontend Visualization page plays it inside the case and always shows the
mock badge when `is_mock` is true.

## Providers

`VIDEO_GENERATION_PROVIDER` selects the implementation via
`app/providers/registry.py`. All implementations take the same **visual-only** prompt, so
the isolation contract is provider-agnostic.

- **`mock`** — the ffmpeg renderer above; `is_mock: true`.
- **`fal`** — the fal.ai aggregator (`FalVideoProvider`): submit to
  `https://queue.fal.run/{model}` with `Authorization: Key`, poll the status URL
  (120 × 5s), fetch the result URL, download the MP4. 401/403 map to a key error, 429 to
  credits, a poll that never completes to a timeout error; the model comes from
  `VIDEO_GENERATION_MODEL`. Real videos skip the mock duration cap: validation runs with
  `expected_duration=0`, and `duration_seconds` is overwritten from the probed file.
- **`kling`, `runway`, `hailuo`** — direct API clients over the same HTTP base
  (pre-existing), each needing `VIDEO_GENERATION_API_KEY` for its own endpoint. Only
  `mock` and `fal` are covered by tests.

Failures surface as a failed `GENERATE_VIDEO` job with the mapped message; nothing is
marked `READY` without a non-empty file on disk.
