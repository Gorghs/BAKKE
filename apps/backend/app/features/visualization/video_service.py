from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.features.visualization.director import VideoDirectorAgent, build_visual_spec
from app.config import get_settings
from app.models import (
    AuditEvent,
    ForensicAnchor,
    GeneratedVideo,
    Hypothesis,
    Scenario,
    ScenarioEvent,
    VideoScenarioSpec,
    VideoShot,
)
from app.adapters.providers import get_video_provider

settings = get_settings()


def _scene_for_mock(spec: dict[str, Any]) -> dict[str, Any]:
    """Map the visual spec onto the schematic floor-plan scene for the MOCK
    video renderer. Only visual information is used."""
    w, h = 960, 540
    characters = []
    n = len(spec.get("characters", []))
    for i, c in enumerate(spec.get("characters", [])):
        # Entry on the left, move through the room to the exit on the right.
        start = (int(w * 0.15), int(h * (0.3 + 0.2 * i)))
        end = (int(w * 0.85), int(h * (0.3 + 0.2 * i)))
        characters.append({"start": start, "end": end, "label": c.get("label", f"Person {i + 1}"), "color": _hex(c.get("color", "#c85a5a"))})
    objects = []
    positions = [(int(w * 0.5), int(h * 0.3)), (int(w * 0.3), int(h * 0.7))]
    for i, o in enumerate(spec.get("objects", [])[:2]):
        objects.append({"pos": positions[i % len(positions)], "label": o.get("label", ""), "color": _hex(o.get("color", "#8a8a95"))})
    unknown_region = [{"x": int(w * 0.5) - 80, "y": int(h * 0.5) - 90, "w": 160, "h": 180}] if spec.get("unknown_periods") else []
    # Move the unknown overlay box to a clean spot to the right of center.
    unknown_region = [{"x": int(w * 0.72), "y": int(h * 0.28), "w": 160, "h": 200}] if spec.get("unknown_periods") else []
    label = spec.get("label", "")
    return {
        "characters": characters,
        "objects": objects,
        "unknown_region": unknown_region,
        "label": label,
    }


def _hex(color: str) -> tuple[int, int, int]:
    try:
        h = color.lstrip("#")
        return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))
    except (ValueError, IndexError):
        return (200, 90, 90)


class VideoService:
    def __init__(self) -> None:
        self.director = VideoDirectorAgent()

    def build_spec(self, db: Session, scenario: Scenario, force: bool = False) -> VideoScenarioSpec:
        spec_row = (
            db.query(VideoScenarioSpec)
            .filter_by(scenario_id=scenario.id)
            .order_by(VideoScenarioSpec.created_at.desc())
            .first()
        )
        if spec_row and spec_row.status == "COMPLETE" and not force:
            return spec_row

        hypothesis = db.get(Hypothesis, scenario.hypothesis_id)
        events = db.query(ScenarioEvent).filter_by(scenario_id=scenario.id).order_by(ScenarioEvent.event_order).all()
        anchors = [
            {"type": a.type, "value": a.value}
            for a in db.query(ForensicAnchor).filter_by(case_id=scenario.case_id).all()
        ]
        scenario.hypothesis_label = hypothesis.hypothesis_id if hypothesis else "H-000"
        spec = build_visual_spec(scenario, events, anchors)
        directed = self.director.direct(spec, events)

        if not spec_row:
            spec_row = VideoScenarioSpec(
                scenario_id=scenario.id,
                case_id=scenario.case_id,
                status="COMPLETE",
                spec=directed,
                visual_prompt=directed.get("visual_prompt", ""),
            )
            db.add(spec_row)
        else:
            spec_row.spec = directed
            spec_row.visual_prompt = directed.get("visual_prompt", "")
            spec_row.status = "COMPLETE"
        db.flush()

        for s in db.query(VideoShot).filter_by(spec_id=spec_row.id).all():
            db.delete(s)
        for shot in directed.get("shots", []):
            db.add(
                VideoShot(
                    spec_id=spec_row.id,
                    shot_index=shot["index"],
                    duration_seconds=shot["duration_seconds"],
                    description=shot["description"],
                    prompt_fragment=shot["description"],
                    status="DIRECTED",
                )
            )
        db.flush()
        return spec_row

    def generate_video(self, db: Session, scenario: Scenario, video_row: GeneratedVideo) -> GeneratedVideo:
        video_row.status = "GENERATING"
        db.flush()
        try:
            spec_row = self.build_spec(db, scenario)
            video_row.spec_id = spec_row.id
            provider = get_video_provider()
            prompt = spec_row.visual_prompt
            video_row.provider = provider.name
            video_row.model = getattr(provider, "model", "")
            video_row.prompt_used = prompt

            out_path = str(Path(settings.video_path) / f"{scenario.id}-{video_row.id}.mp4")
            duration = max(spec_row.spec.get("total_duration", 12.0), 6.0)
            if provider.is_mock:
                duration = min(duration, 12.0)
            scene = _scene_for_mock(spec_row.spec) if provider.is_mock else None
            result = provider.generate(prompt, out_path, duration, scene) if provider.is_mock else provider.generate(prompt, out_path, duration)
            video_row.video_path = result.get("path", out_path)
            video_row.duration_seconds = result.get("duration", duration)
            video_row.format = result.get("format", "mp4")
            video_row.is_mock = bool(result.get("is_mock", provider.is_mock))
            video_row.label_text = (
                f"BAKKE | {spec_row.spec.get('label', '')} | 3D ANIMATED SCENARIO VISUALIZATION | NOT RECORDED FOOTAGE"
            )
            dims = _probe_video(video_row.video_path)
            video_row.width = dims["width"]
            video_row.height = dims["height"]
            video_row.validation = self.validate(video_row.video_path, spec_row.spec)
            video_row.status = "READY" if video_row.validation.get("ok") else "INVALID"
            db.add(
                AuditEvent(
                    case_id=scenario.case_id,
                    action="video_generated",
                    agent="VideoDirectorAgent/VideoGenerationProvider",
                    provider=provider.name,
                    output_object_id=video_row.id,
                    summary=f"3D animated scenario video generated ({provider.name}, {'mock' if video_row.is_mock else 'real'})",
                    extra={"duration": video_row.duration_seconds},
                )
            )
            db.flush()
            return video_row
        except Exception as exc:
            video_row.status = "FAILED"
            video_row.error = str(exc)[:2000]
            db.add(
                AuditEvent(
                    case_id=scenario.case_id,
                    action="video_generation_failed",
                    agent="VideoGenerationProvider",
                    summary=str(exc)[:400],
                    output_object_id=video_row.id,
                )
            )
            db.flush()
            return video_row

    def validate(self, video_path: str, spec: dict[str, Any]) -> dict[str, Any]:
        """Validate generated video: exists, not corrupt, correct duration/aspect/format."""
        from pathlib import Path

        p = Path(video_path)
        checks = {"exists": p.exists(), "size_bytes": p.stat().st_size if p.exists() else 0}
        if not checks["exists"] or checks["size_bytes"] == 0:
            checks["ok"] = False
            checks["errors"] = ["video file missing or empty"]
            return checks
        try:
            import subprocess

            probe = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration:stream=width,height,codec_name",
                    "-of",
                    "json",
                    video_path,
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            import json

            data = json.loads(probe.stdout)
            streams = data.get("streams", [])
            duration = float(data.get("format", {}).get("duration", 0) or 0)
            video_stream = next((s for s in streams if s.get("codec_name")), None)
            width = int(video_stream.get("width", 0)) if video_stream else 0
            height = int(video_stream.get("height", 0)) if video_stream else 0
            expected = min(max(spec.get("total_duration", 6.0), 4.0), 12.0)
            checks.update(
                {
                    "ok": duration > 0 and width > 0 and height > 0,
                    "duration": round(duration, 2),
                    "width": width,
                    "height": height,
                    "codec": video_stream.get("codec_name", "") if video_stream else "",
                    "aspect_ratio": "16:9" if width and height else "unknown",
                    "note": "AI visual validation is secondary; the scenario specification remains authoritative.",
                }
            )
            checks["errors"] = []
            if duration < expected - 1:
                checks["errors"].append(f"duration {duration}s shorter than expected {expected}s")
                checks["ok"] = False
            return checks
        except Exception as exc:
            checks["ok"] = False
            checks["errors"] = [str(exc)[:300]]
            return checks


def _probe_video(video_path: str) -> dict[str, int]:
    try:
        import json
        import subprocess

        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "stream=width,height", "-of", "json", video_path],
            capture_output=True,
            text=True,
        )
        data = json.loads(probe.stdout)
        s = next((x for x in data.get("streams", []) if x.get("width")), {})
        return {"width": int(s.get("width", 0)), "height": int(s.get("height", 0))}
    except Exception:
        return {"width": 0, "height": 0}