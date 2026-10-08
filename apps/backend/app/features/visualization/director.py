from __future__ import annotations

from typing import Any

from app.infrastructure.agents.base import BaseAgent
from app.models import Scenario, ScenarioEvent


class VideoDirectorAgent(BaseAgent):
    """Turns a validated scenario's *visual* specification into a shot list and a
    detailed, visual-only video-generation prompt.

    This agent never receives the full case, evidence, reports or reasoning.
    """

    name = "VideoDirectorAgent"

    SHOT_DURATION = 4.0

    def direct(self, spec: dict[str, Any], events: list[ScenarioEvent]) -> dict[str, Any]:
        shots = self._build_shots(spec, events)
        spec["shots"] = shots
        spec["total_duration"] = round(sum(s["duration_seconds"] for s in shots), 1)
        prompt = self._build_prompt(spec)
        spec["visual_prompt"] = prompt
        return spec

    def _build_shots(self, spec: dict[str, Any], events: list[ScenarioEvent]) -> list[dict[str, Any]]:
        shots: list[dict[str, Any]] = []
        # Establish shot: environment only, no characters.
        shots.append(
            {
                "index": 1,
                "duration_seconds": 4.0,
                "description": f"Establishing view of {spec['environment']['description']}.",
                "camera": "wide static establishing shot, stable, eye level",
                "action": [],
            }
        )
        idx = 2
        for ev in events:
            event_type = ev.event_type  # KNOWN/INFERRED/UNKNOWN/HYPOTHESIZED
            desc = ev.description
            if event_type == "KNOWN":
                action = [{"description": desc, "supported": True}]
                camera = "medium shot, slow controlled pan following the action"
            elif event_type == "INFERRED":
                action = [{"description": desc, "supported": False, "note": "inferred"}]
                camera = "medium shot, stable, neutral framing"
            elif event_type == "HYPOTHESIZED":
                action = [{"description": desc, "supported": False, "note": "hypothesized"}]
                camera = "medium shot, neutral framing"
            else:
                action = [{"description": "EVENT NOT ESTABLISHED", "supported": False, "note": "unknown period"}]
                camera = "slow neutral transition; label 'EVENT NOT ESTABLISHED'"
            shots.append(
                {
                    "index": idx,
                    "duration_seconds": self.SHOT_DURATION,
                    "description": desc[:500],
                    "camera": camera,
                    "action": action,
                }
            )
            idx += 1
        return shots

    def _build_prompt(self, spec: dict[str, Any]) -> str:
        env = spec["environment"]
        chars = spec.get("characters", [])
        objects = spec.get("objects", [])
        shots = spec.get("shots", [])
        unknown = spec.get("unknown_periods", [])
        constraints = spec.get("constraints", [])

        char_lines = "\n".join(
            f"- {c['label']}: {c.get('appearance', 'neutral generic adult')}, {c.get('clothing', 'neutral clothing')}"
            for c in chars
        )
        object_lines = "\n".join(f"- {o['label']}: {o.get('description', '')}" for o in objects)
        shot_lines = "\n".join(
            f"Shot {s['index']:02d} ({s['duration_seconds']}s): {s['description']}. Camera: {s['camera']}."
            for s in shots
        )
        unknown_lines = "\n".join(f"- {u}" for u in unknown) if unknown else "- none"

        return f"""Create a high-quality 3D animated visualization.

ENVIRONMENT:
{env.get('description', 'Neutral interior')}
Time of day: {env.get('time_of_day', 'evening')}
Lighting: {env.get('lighting', 'neutral controlled lighting')}

CHARACTERS:
{char_lines}

OBJECTS:
{object_lines}

SHOT LIST:
{shot_lines}

UNKNOWN PERIODS:
{unknown_lines}

ANIMATION:
Professional semi-realistic 3D animation. Neutral generic characters.
Realistic proportions. Clean environment. Clear spatial relationships.
Smooth controlled motion. Stable camera. Minimal cinematic effects.
No live-action appearance. No CCTV appearance. No documentary appearance.

CONSTRAINTS:
{' '.join(constraints) or 'Do not add people. Do not add objects. Do not change positions. Do not invent actions. Do not invent events. Do not introduce unsupported interactions.'}
Do not invent motives.
Do not invent facial expressions implying intent.
Do not invent events during unknown periods.
Do not change forensic spatial anchors.
No gore. No exaggerated acting. No cinematic violence.

DURATION:
{spec.get('total_duration', 12.0)} seconds total.

OUTPUT:
{spec.get('aspect_ratio', '16:9')}
High-quality 3D animated video. Label overlay: "BAKKE | {spec.get('label', '')} | 3D ANIMATED SCENARIO VISUALIZATION | NOT RECORDED FOOTAGE"."""


def build_visual_spec(scenario: Scenario, events: list[ScenarioEvent], anchors: list[dict[str, Any]]) -> dict[str, Any]:
    """Build a visual-only production spec from a validated scenario.

    Derives the spatial map (environment, object positions) purely from the
    scenario's own visual content: locations named in events and the scenario's
    participants. Deliberately excludes: evidence IDs, reports, witness
    statements, RAG context, similar cases, scores, reasoning text, and forensic
    anchor values — `anchors` is accepted for call compatibility but is never
    read into the spec.
    """
    participants = scenario.participants or []
    characters = []
    palette = ["#c85a5a", "#5a8ac8", "#6fbf6f", "#c8a85a"]
    for i, p in enumerate(participants[:4]):
        characters.append(
            {
                "id": f"char_{i + 1}",
                "label": p if len(p) <= 16 else f"Person {i + 1}",
                "appearance": "neutral generic adult human, semi-realistic proportions",
                "clothing": "neutral, muted colors",
                "color": palette[i % len(palette)],
            }
        )

    # Spatial map: distinct locations named by the scenario's own events.
    locations: list[str] = []
    seen_loc: set[str] = set()
    for ev in events:
        loc = (ev.location or "").strip().title()
        if loc and loc not in seen_loc:
            seen_loc.add(loc)
            locations.append(loc)

    objects = []
    grid_cols = max(len(locations), 2)
    for i, loc in enumerate(locations[:8]):
        col = i % grid_cols
        row = i // grid_cols
        fx = 0.15 + (0.7 * (col + 0.5) / grid_cols)
        fy = 0.2 + 0.18 * row
        objects.append(
            {
                "label": loc[:30],
                "description": f"Location marker: {loc}",
                "color": "#8a8a95",
                "pos": [round(fx, 3), round(min(fy, 0.72), 3)],
            }
        )

    unknown_periods = [
        "EVENT NOT ESTABLISHED - events in this period are not supported by the available evidence"
    ]

    if locations:
        env_description = "An interior scene comprising: " + ", ".join(locations[:6]) + "."
    else:
        env_description = "A single interior location."

    environment = {
        "type": "interior",
        "description": env_description,
        "time_of_day": "evening",
        "lighting": "neutral controlled lighting",
    }

    return {
        "label": f"HYPOTHESIS {getattr(scenario, 'hypothesis_label', '') or '?'}",
        "title": scenario.summary[:200],
        "environment": environment,
        "locations": locations,
        "characters": characters,
        "objects": objects,
        "unknown_periods": unknown_periods,
        "aspect_ratio": "16:9",
        "constraints": [
            "Do not add people.",
            "Do not add objects.",
            "Do not move objects to unsupported positions.",
            "Do not create unsupported actions or interactions.",
        ],
        "visual_only": True,
    }