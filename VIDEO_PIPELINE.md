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
  string. The JSON holds `visual_prompt` (expanded, sent to the provider),
  `visual_prompt_director` (raw director output), `prompt_expansion` (provider, model,
  chars, fallback reason) and a JSON `shots` list (each shot: index, duration,
  description). No `injury_region` or top-level `locations` keys — `test_video_isolation.py`
  asserts the spec contains no `E-00x` evidence ids, no report excerpts, and no forensic
  reasoning.
- Every render is labelled `NOT RECORDED FOOTAGE`.

## Prompt expansion

`build_spec` runs the director prompt through `expand_visual_prompt`
(`app/services/video_service.py`):

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
        │    ├─ build_visual_spec + director  ──▶ raw visual prompt (visual-only)
        │    └─ expand_visual_prompt          ──▶ provider-tailored prompt (fallback-safe)
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
