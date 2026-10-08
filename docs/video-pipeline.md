# Video Pipeline

## Goal

Produce a **labelled 3D animated reconstruction** of a surviving scenario. The video is
explicitly **not recorded footage** and must never leak the case's forensic reasoning.

## Isolation contract

- The **director** (`app/features/visualization/director.py`) receives only the scenario's visual content:
  locations, objects, actors, timing windows, and camera descriptors.
- It never receives case reports, evidence IDs, fact sources, or reasoning text.
- The spec (`VideoScenarioSpec`) stores a single `visual_prompt` string plus a JSON
  `shots` list (each shot: index, duration, description).
- Every render is labelled `NOT RECORDED FOOTAGE`. `test_video_isolation.py` asserts the
  spec contains no `E-00x` evidence ids, no report excerpts, and no forensic reasoning.

## Renderer

`app/infrastructure/providers/schematic.py` (mock) renders with ffmpeg:

- Resolution **640×360**, **12 fps**, deterministic seeded colors/shapes per actor.
- Mock duration is **capped at 12 seconds** (`duration = min(duration, 12.0)`); the
  pipeline scales shots to fit.
- Shot construction: clear frame, draw shapes moving per timing windows, overlay location
  + timecode + `NOT RECORDED FOOTAGE` label, crossfade between shots.
- Validation caps the expected duration to the same bound.

## Data flow

```
surviving scenario
   └─▶ infrastructure/jobs/tasks.py GENERATE_VIDEO
        ├─ create GeneratedVideo(status=PENDING)   # spec_id nullable until built
        ├─ VideoService.build_spec(scenario)  ──▶ VideoScenarioSpec (visual-only)
        ├─ video.spec_id = spec.id
        └─ VideoService.generate_video(...)   ──▶ MP4 on disk + status READY
```

The video record stores provider, model, width/height, format, duration, size, label and
a `is_mock` flag. The API streams it via `GET /api/videos/{vid}/stream` with Range
support. The frontend Visualization page plays it inside the case and always shows the
mock badge when `is_mock` is true.

## Real provider hooks

`VIDEO_GENERATION_PROVIDER` selects the implementation via
`app/infrastructure/providers/registry.py`. A real provider would receive the same **visual-only** spec
(the prompt + shots) and return the final MP4; the isolation contract is provider-agnostic.
