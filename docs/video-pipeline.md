# Video Pipeline

## Goal

Produce a **labelled 3D animated reconstruction** of a surviving scenario. The video is
explicitly **not recorded footage** and must never leak the case's forensic reasoning.

## Isolation contract

- The **director** (`app/features/visualization/director.py`) receives only the scenario's visual content:
  locations, objects, actors, timing windows, and camera descriptors.
- It never receives case reports, evidence IDs, fact sources, or reasoning text.
- The spec row (`VideoScenarioSpec`) stores a `visual_prompt` string plus a `spec` JSON
  document (characters, objects, unknown-region boxes, label, total duration); directed
  shots are stored as `VideoShot` rows (index, duration, description, prompt fragment).
- Every render is labelled `NOT RECORDED FOOTAGE`. `test_video_isolation.py` asserts the
  spec contains no `E-00x` evidence ids, no report excerpts, and no forensic reasoning.

## Renderer

`app/adapters/media/schematic.py` (mock) renders with ffmpeg:

- Resolution **640×360**, **12 fps**; shapes and colors are derived deterministically
  from the scene description, so the same spec renders the same frames.
- Render duration is `max(spec total_duration, 6s)`, capped at **12 seconds** for the
  mock (`VideoService.generate_video`).
- Frames are drawn procedurally: character shapes move from entry to exit, static
  objects carry labels, an unknown region pulses, and a bottom bar shows the scenario
  label plus `3D ANIMATED SCENARIO VISUALIZATION - NOT RECORDED FOOTAGE`.
- Validation caps the expected duration to the same bound.

## Data flow

```
surviving scenario
   └─▶ jobs/tasks.py GENERATE_VIDEO → GenerateVideoWorkflow
        ├─ create GeneratedVideo(status=PENDING)   # spec_id nullable until built
        ├─ VideoService.build_spec(scenario)  ──▶ VideoScenarioSpec (visual-only)
        ├─ video.spec_id = spec.id
        ├─ VideoService.generate_video(...)   ──▶ MP4 on disk + status READY
        └─ write replay manifest (data/replay/{case}.video_{scenario}.json)
```

The video record stores provider, model, dimensions, format, duration, label text,
validation results (existence, byte size, duration bounds) and an `is_mock` flag. The API
streams it via `GET /api/videos/{vid}/stream` with Range support. The frontend
Visualization page plays it inside the case and always shows the mock badge when
`is_mock` is true.

## Real provider hooks

`VIDEO_GENERATION_PROVIDER_TYPE` selects the implementation through the adapter
catalogue (`app/adapters/providers/__init__.py`): `mock` (schematic ffmpeg clip) or a
vendor adapter — `kling`, `runway`, `hailuo`
(`app/adapters/media/vendor_video.py`, requires `VIDEO_GENERATION_API_KEY`).
A live provider receives the same **visual-only** prompt (the director's text, which
embeds the shot list) plus the render duration, and returns the final MP4; the isolation
contract is provider-agnostic. If the key is missing the adapter raises instead of
falling back to the mock.
