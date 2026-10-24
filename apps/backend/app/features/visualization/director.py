from __future__ import annotations

import re
from typing import Any

from app.infrastructure.agents.base import BaseAgent
from app.features.visualization.visual_brief import (
    DUMMY_APPEARANCE,
    DUMMY_CLOTHING,
    GONE_STATES,
    derive_visual_brief,
    present_tense,
)
from app.models import Scenario, ScenarioEvent

# Coarse day periods used to describe light without inventing a time of day.
_TIME_PERIODS = (
    (5, 9, "early morning"),
    (9, 12, "late morning"),
    (12, 16, "afternoon"),
    (16, 19, "late afternoon"),
    (19, 22, "evening"),
)


def _clock_hour(clock: str) -> int | None:
    raw = str(clock or "").strip()
    if ":" not in raw:
        return None
    try:
        hour = int(raw.split(":", 1)[0])
    except ValueError:
        return None
    return hour if 0 <= hour <= 23 else None


def _time_period(clock: str) -> str:
    hour = _clock_hour(clock)
    if hour is None:
        return ""
    for start, end, label in _TIME_PERIODS:
        if start <= hour < end:
            return label
    return "night"


def _clock_values(event: ScenarioEvent) -> list[str]:
    """Clock times attached to one event, in the order the scenario states them.

    Extraction stores timing as whatever keys the evidence produced, so this
    reads the common ones and splits a range such as "19:12-07:50" into its ends.
    """
    timing = event.timing or {}
    values: list[str] = []
    for key in ("start", "end", "time", "period", "window", "from", "to"):
        raw = timing.get(key)
        if raw is None or raw == "":
            continue
        for part in re.split(r"\s*(?:-|–|—|to|until)\s*", str(raw).strip()):
            if _clock_hour(part) is not None and part not in values:
                values.append(part)
    return values


def _clock_minutes(clock: str) -> int | None:
    hour = _clock_hour(clock)
    if hour is None:
        return None
    try:
        minute = int(str(clock).split(":", 1)[1])
    except (IndexError, ValueError):
        return None
    return hour * 60 + minute


def _timeline(events: list[ScenarioEvent]) -> list[str]:
    """The scenario's clock times in the order they happened.

    A clock range orders itself: its start comes before its end, and an end that
    reads earlier than the start crossed midnight. Single clocks are placed on
    the day of the window they belong to. Row order is not used, because the
    extraction does not promise it: storing "07:50" before the "19:12 to 07:50"
    window used to describe the morning as coming before the evening.
    """
    windows: list[tuple[str, str, int]] = []
    singles: list[str] = []
    for event in events:
        values = _clock_values(event)
        if len(values) >= 2:
            start, end = values[0], values[-1]
            start_minutes, end_minutes = _clock_minutes(start), _clock_minutes(end)
            if start_minutes is None or end_minutes is None:
                continue
            windows.append((start, end, 1 if end_minutes < start_minutes else 0))
        elif values:
            singles.append(values[0])

    days: dict[str, int] = {}
    for start, end, end_day in windows:
        days.setdefault(start, 0)
        # An endpoint that one window already placed on a later day keeps it.
        days[end] = max(days.get(end, 0), end_day)
    for clock in singles:
        days.setdefault(clock, 0)
    ordered = sorted(days.items(), key=lambda item: (item[1], _clock_minutes(item[0]) or 0))
    return [clock for clock, _ in ordered]


def _event_clock(event: ScenarioEvent) -> str:
    """The event's own clock time, visual content only, or an empty string."""
    values = _clock_values(event)
    if len(values) >= 2:
        return f"{values[0]} to {values[-1]}"
    return values[0] if values else ""


def _clock_span(events: list[ScenarioEvent]) -> tuple[str, str]:
    """Describe the scenario's clock window as time of day plus a window string.

    Only timestamps already attached to the scenario's events are read, so the
    director never asserts a time the scenario does not state.
    """
    clocks = _timeline(events)
    if not clocks:
        return "one continuous period, no clock time stated", ""
    if len(clocks) == 1:
        period = _time_period(clocks[0]) or "one continuous period"
        return f"{period}, a single moment at {clocks[0]}", clocks[0]
    first, last = clocks[0], clocks[-1]
    first_period = _time_period(first) or "one period"
    last_period = _time_period(last)
    window = f"{first} to {last}"
    if last_period and last_period != first_period:
        return f"{first_period} ({first}) through {last_period} ({last})", window
    return f"{first_period} ({window})", window


def _last_clock(events: list[ScenarioEvent]) -> str:
    clocks = _timeline(events)
    return clocks[-1] if clocks else ""


def _with_article(phrase: str, fallback: str = "the space") -> str:
    """Read a place name as a noun phrase: "the yard", never "the the yard"."""
    text = str(phrase or "").strip()
    if not text:
        return fallback
    return text if text.lower().startswith("the ") else f"the {text}"


def _sentence(text: str) -> str:
    text = (text or "").strip()
    return text[:1].upper() + text[1:] if text else text


def _bullet(line: str) -> str:
    text = (line or "").strip().rstrip(".")
    return f"- {_sentence(text)}." if text else ""


class VideoDirectorAgent(BaseAgent):
    """Turns a validated scenario's *visual* specification into a shot list and a
    detailed, visual-only video-generation prompt.

    This agent never receives the full case, evidence, reports or reasoning.
    """

    name = "VideoDirectorAgent"

    # The bridge returns one fixed-length clip of about 10 seconds and ignores
    # any requested duration, so the shot list has to fit that window.
    TARGET_TOTAL_SECONDS = 10.0
    MIN_SHOT_SECONDS = 1.5
    # Longer than this and the model stops following the beat and improvises.
    MAX_SHOT_SECONDS = 6.0
    ESTABLISHING_SECONDS = 2.0
    MAX_ESTABLISHING_SECONDS = 4.0
    END_STATE_SECONDS = 2.5
    MAX_SHOTS = 5

    def direct(self, spec: dict[str, Any], events: list[ScenarioEvent]) -> dict[str, Any]:
        shots = self._build_shots(spec, events)
        spec["shots"] = shots
        spec["total_duration"] = round(sum(s["duration_seconds"] for s in shots), 1)
        spec["visual_prompt"] = self._build_prompt(spec)
        return spec

    # ---------------------------------------------------------------- shots

    def _figure_ref(self, spec: dict[str, Any], label: str) -> str:
        chars = spec.get("characters", [])
        if len(chars) <= 1:
            return "the figure"
        return f"the {label.lower()}" if label else "the figure"

    def _build_shots(self, spec: dict[str, Any], events: list[ScenarioEvent]) -> list[dict[str, Any]]:
        env = spec.get("environment", {})
        space = env.get("description") or "the space"
        window = env.get("time_window", "")
        chars = spec.get("characters", [])
        props = spec.get("props", [])
        beats = spec.get("beats", [])
        space_phrase = _with_article(space)
        shots: list[dict[str, Any]] = []

        # 1. Establishing shot: the space and the props in their start state.
        start_props = [p for p in props if p.get("start_state") == "present"]
        in_frame = [
            f"exactly one {p['label']}"
            + (f" on the {p['location']}" if p.get("location") else "")
            for p in start_props
        ]
        establishing_description = f"Wide view of {space_phrase}."
        if in_frame:
            establishing_description += " " + _sentence("; ".join(in_frame)) + "."
        timeline = _timeline(events)
        first_clock = timeline[0] if timeline else ""
        shots.append(
            {
                "kind": "establishing",
                "description": establishing_description,
                "framing": "wide establishing shot, 24-28mm equivalent, deep focus, eye level",
                "camera": "locked-off wide with a five percent push-in across the shot, no shake",
                "direction": (
                    "Let the layout, the surfaces and the position of each area read before "
                    "anything moves. No action and no object changes."
                ),
                "action": [],
                "clock": first_clock,
            }
        )

        # 2. One shot per action beat, in order. The tenth second has to carry an
        #    establishing shot and, when an object changes, an end-state shot, so
        #    the beats get the slots that remain and fold into each other rather
        #    than pushing the clip past MAX_SHOTS.
        end_props = [
            p for p in props if p.get("end_state") and p["end_state"] != p.get("start_state")
        ]
        action_slots = self.MAX_SHOTS - 1 - (1 if end_props else 0)
        beats = self._fold_beats(beats, action_slots)

        # A beat without its own clock inherits the one before it. Printing the
        # whole window instead stamped a removal that takes seconds with an
        # eleven-hour range.
        beat_clock = ""
        for i, beat in enumerate(beats):
            actor = beat.get("actor") or (chars[0]["label"] if chars else "")
            figure = self._figure_ref(spec, actor)
            action_text = _sentence(f"{figure} {present_tense(str(beat.get('action') or ''))}") + "."
            if i == 0:
                framing = "medium wide shot, 35mm equivalent, the figure enters from frame left"
                camera = "slow tracking move at walking pace that follows the figure without anticipating it"
                direction = (
                    "Start with the figure out of frame and let them step into it at a normal "
                    "walking pace. The figure is a hypothesis, so play it plainly: no performance, "
                    "no expression, no hesitation."
                )
            else:
                framing = "medium close shot, 50mm equivalent, hands and the object in the lower third"
                camera = "locked-off medium close with a slight drift, the action stays centred"
                direction = (
                    "Show the action on the object itself. Keep the face out of frame; the hands "
                    "and the object carry the beat."
                )
            if i == 0:
                in_frame = f"{_sentence(space_phrase)}, with {figure} in frame."
            else:
                where = next(
                    (str(p["location"]) for p in props if p.get("location")), space
                )
                in_frame = f"Close on {_with_article(where)}, with the figure's hands in frame."
            beat_clock = str(beat.get("clock") or "").strip() or beat_clock
            shots.append(
                {
                    "kind": "action",
                    "description": in_frame,
                    "framing": framing,
                    "camera": camera,
                    "direction": direction,
                    "action": [{"description": action_text, "supported": False, "note": "hypothesized"}],
                    "clock": beat_clock,
                }
            )

        # 3. End-state shot: what the objects look like after the beat.
        if end_props:
            clock = _last_clock(events) or window
            period = _time_period(clock)
            states = "; ".join(self._state_phrase(p) for p in end_props)
            shots.append(
                {
                    "kind": "state",
                    "description": (
                        f"The same space in {period or 'the same'} light. {_sentence(states)}."
                    ),
                    "framing": "wide shot from the same angle as the first shot, 24-28mm equivalent",
                    "camera": "locked-off wide with a very slow drift, nothing enters or leaves",
                    "direction": (
                        "Hold on the space and let the change read as a state of the space. "
                        "Nothing moves except the light."
                    ),
                    "action": [],
                    "clock": clock,
                }
            )

        # 4. A scenario with no action and no state change still needs a second
        #    shot, or the tail of the clip is left undescribed.
        if len(shots) == 1:
            shots.append(
                {
                    "kind": "hold",
                    "description": f"The same space: {space_phrase}, unchanged.",
                    "framing": "medium wide shot from a second angle, 35mm equivalent",
                    "camera": "slow lateral drift, no shake, nothing enters or leaves",
                    "direction": "Hold the space. Invent nothing.",
                    "action": [],
                    "clock": window,
                }
            )

        self._assign_times(shots)
        return shots

    def _fold_beats(self, beats: list[dict[str, Any]], slots: int) -> list[dict[str, Any]]:
        """Fit the beats into the action shots the clip can hold.

        Every stated action has to appear, so the tail folds into one shot with
        the actions joined in order rather than being dropped.
        """
        if slots <= 0 or not beats:
            return []
        if len(beats) <= slots:
            return beats
        head = beats[: slots - 1]
        tail = beats[slots - 1 :]
        folded = {
            "clock": tail[0].get("clock", ""),
            "actor": tail[0].get("actor", ""),
            "action": ", then ".join(str(b.get("action") or "") for b in tail),
        }
        return head + [folded]

    def _state_phrase(self, prop: dict[str, Any]) -> str:
        label = str(prop.get("label") or "object")
        where = f" on the {prop['location']}" if prop.get("location") else ""
        state = str(prop.get("end_state") or "").lower()
        if state in GONE_STATES:
            return f"no {label} is{where}" if where else f"no {label} is in frame"
        if state in ("open", "unlocked"):
            return f"the {label}{where} stands open"
        if state in ("closed", "locked"):
            return f"the {label}{where} stands closed"
        return f"the {label}{where} is {state}"

    def _assign_times(self, shots: list[dict[str, Any]]) -> None:
        n_action = sum(1 for s in shots if s["kind"] == "action")
        has_end = any(s["kind"] == "state" for s in shots)
        total = self.TARGET_TOTAL_SECONDS
        establishing = self.ESTABLISHING_SECONDS
        end = self.END_STATE_SECONDS if has_end else 0.0

        if n_action:
            available = total - establishing - end
            per_action = available / n_action
            if per_action > self.MAX_SHOT_SECONDS:
                per_action = self.MAX_SHOT_SECONDS
                leftover = available - per_action * n_action
                establishing = min(self.MAX_ESTABLISHING_SECONDS, establishing + leftover)
            elif per_action < self.MIN_SHOT_SECONDS:
                per_action = self.MIN_SHOT_SECONDS
                establishing = max(1.0, total - end - per_action * n_action)
            durations = [establishing] + [per_action] * n_action + ([end] if has_end else [])
        elif has_end:
            durations = [4.0, total - 4.0]
        else:
            durations = [total / 2, total / 2]

        durations = [round(d, 1) for d in durations]
        durations[-1] = round(durations[-1] + (total - sum(durations)), 1)

        cursor = 0.0
        for index, (shot, duration) in enumerate(zip(shots, durations), start=1):
            shot["index"] = index
            shot["start_seconds"] = round(cursor, 1)
            cursor += duration
            shot["end_seconds"] = round(cursor, 1)
            shot["duration_seconds"] = round(duration, 1)

    # --------------------------------------------------------------- prompt

    def _build_prompt(self, spec: dict[str, Any]) -> str:
        env = spec.get("environment", {})
        chars = spec.get("characters", [])
        props = spec.get("props", [])
        beats = spec.get("beats", [])
        shots = spec.get("shots", [])
        if shots:
            cursor = 0.0
            for index, s in enumerate(shots, start=1):
                s.setdefault("index", index)
                if s.get("start_seconds") is None:
                    dur = float(s.get("duration_seconds") or 0) or 1.0
                    s["start_seconds"] = round(cursor, 1)
                    cursor += dur
                    s["end_seconds"] = round(cursor, 1)
                    s["duration_seconds"] = round(dur, 1)
                s.setdefault("clock", "")
        continuity = spec.get("continuity", [])
        absences = spec.get("absences", [])
        total = spec.get("total_duration", 10.0)

        subject_lines = "\n".join(
            f"- {c['label']}: {c.get('appearance', DUMMY_APPEARANCE)}. "
            f"{_sentence(c.get('clothing', DUMMY_CLOTHING))}. Keep the same body, surface and "
            "wardrobe in every shot; no facial detail at any point."
            for c in chars
        ) or "- None. The clip shows the space and the objects only."

        object_lines: list[str] = []
        for prop in props:
            label = str(prop["label"])
            where = f" on the {prop['location']}" if prop.get("location") else ""
            start = str(prop.get("start_state") or "")
            end = str(prop.get("end_state") or "")
            if end in GONE_STATES:
                object_lines.append(
                    f"- {label.capitalize()}: exactly one{where}, in place from the first frame. "
                    f"It leaves the frame only in the shot that shows the removal, and no {label} "
                    "appears after that."
                )
            elif start and end and start != end:
                object_lines.append(f"- {label.capitalize()}: {start} at the start, {end} at the end.")
            elif end:
                object_lines.append(f"- {label.capitalize()}: {end} for the whole clip.")
            else:
                object_lines.append(
                    f"- {label.capitalize()}: fixed in place; it moves only where a shot says it moves."
                )
        object_block = "\n".join(object_lines) or "- None beyond the space itself."

        story = ""
        if beats:
            actions = ", then ".join(present_tense(str(b.get("action") or "")) for b in beats)
            story = (
                "STORY:\nThis clip visualises one hypothesis. In order: the figure "
                f"{actions}.\n\n"
            )

        # The scenario's own clock goes on screen so the viewer can read the time
        # without guessing it from the light. It is the shot's stated clock, never
        # a running counter, and never a clock the scenario does not state.
        timed_shots = [s for s in shots if s.get("clock")]

        shot_blocks: list[str] = []
        for i, s in enumerate(shots):
            clock = f" | clock {s['clock']}" if s.get("clock") else ""
            if timed_shots:
                stamp = f"  On-screen timecode: {s['clock'] or 'no timecode'}\n"
            else:
                stamp = ""
            action = " ".join(a.get("description", "") for a in s.get("action", []))
            if not action:
                action = "Nothing moves."
            if i + 1 < len(shots):
                transition = f"Hard cut to shot {shots[i + 1]['index']:02d}."
            else:
                transition = "Hold the last frame to the end of the clip."
            shot_blocks.append(
                f"Shot {s['index']:02d} - {s['start_seconds']:.1f}s to {s['end_seconds']:.1f}s"
                f" ({s['duration_seconds']}s){clock}\n"
                f"  Framing: {s.get('framing', 'neutral framing')}.\n"
                f"  In frame: {s['description']}\n"
                f"{stamp}"
                f"  Action: {action}\n"
                f"  Direction: {s.get('direction', 'Neutral, literal staging.')}\n"
                f"  Camera and motion: {s.get('camera', 'static')}.\n"
                f"  Transition: {transition}"
            )
        shot_lines = "\n".join(shot_blocks)

        continuity_lines = "\n".join(
            bullet for bullet in (_bullet(line) for line in continuity) if bullet
        ) or "- none"
        continuity_lines += (
            "\n- Same space, same objects and same figure in every shot; the geography never changes."
        )

        constraints = list(spec.get("constraints", []))
        if chars:
            constraints.append("Use only the figures in SUBJECTS. Add no other people.")
        else:
            constraints.append("Do not add people.")
        if props:
            constraints.append(
                "Use only the objects in OBJECTS. Add no other props, tools or set dressing."
            )
        for noun in absences:
            constraints.append(f"Do not show any {noun}.")
        if spec.get("unknown_periods"):
            constraints.append(
                "Where the shot list leaves a period undescribed, leave it visually empty and "
                "add no activity to fill it."
            )
        if timed_shots:
            constraints.append(
                "The only text in the clip is the on-screen timecode in the top right corner and "
                "the label overlay at the end. Render no other words, digits, signage or captions, "
                "and never restyle or move the timecode."
            )
        constraints.extend(
            [
                "Do not invent intent, inner states or facial expressions.",
                "Do not move the camera to a place the shot list does not name.",
                "No gore. No exaggerated acting. No cinematic violence.",
            ]
        )

        time_lines = [f"Time of day: {env.get('time_of_day', 'one continuous period')}."]
        if env.get("time_window"):
            time_lines.append(
                f"Clock window: {env['time_window']}. Map it onto the shot timestamps below; "
                "the light changes only as that window advances."
            )
        time_lines.append(
            f"Lighting: {env.get('lighting', 'neutral controlled lighting')}. Keep one light "
            "direction per shot, let shadows read, and avoid unmotivated colour shifts."
        )
        if timed_shots:
            time_lines.append(
                "On-screen timecode: the clock named for each shot, in small monospace white "
                "digits on a thin dark translucent plate, in the top right corner, fully inside "
                "the frame, at the same position and size in every shot that carries one. It "
                "holds that reading for the whole shot."
            )

        look = (
            "Stylised 3D animation with dummy figures: smooth matte surfaces, simplified anatomy, "
            "no skin texture, no facial expression, no photorealism. The result must read as a "
            "reconstruction of a space, not as footage of a person."
            if chars
            else "Stylised 3D animation: clean matte surfaces, simplified geometry, no photorealism."
        )
        look += (
            "\nMatte surfaces with light wear, physically based lighting, a restrained palette, "
            "35-50mm equivalent framing, shallow depth of field on the medium shots and deep focus "
            "on the wide, subtle grain, stable horizon. No lens flares, no slow motion, no grade "
            "that hides detail. Each shot must differ visibly in angle or distance from the one "
            "before it; never repeat the same framing."
        )

        return f"""One location, one continuous 3D animated reconstruction, cut into the shots below.

SETTING:
{_sentence(env.get('description', 'a single interior space'))}. Treat this as one location rather than a
montage: establish its size, depth and the relative position of every area in the first shot,
then keep that geography fixed.

{story}TIME OF DAY:
{chr(10).join(time_lines)}

SUBJECTS:
{subject_lines}

OBJECTS:
{object_block}

SHOT LIST:
Shot timestamps are clip time. A clock time is the scenario's own time for that beat; it
labels the shot, and the shot shows that moment rather than playing out the hours between
two clocks.

{shot_lines}

CONTINUITY:
{continuity_lines}

LOOK AND FEEL:
{look}

ANIMATION:
Clear spatial relationships. Hard cuts between shots are allowed; within a shot nothing jumps
in position, light or wardrobe. Smooth controlled motion, stable camera, minimal cinematic
effects. No live action, no CCTV, no documentary appearance.

CONSTRAINTS:
{' '.join(constraints)}
Do not add events the shot list does not name.

DURATION:
{total} seconds in total, cut exactly as the shot timestamps above describe.

OUTPUT:
{spec.get('aspect_ratio', '16:9')} aspect ratio. High-quality 3D animated video. Label overlay: "BAKKE | {spec.get('label', '')} | 3D ANIMATED SCENARIO VISUALIZATION | NOT RECORDED FOOTAGE"."""


def build_visual_spec(
    scenario: Scenario,
    events: list[ScenarioEvent],
    anchors: list[dict[str, Any]],
    brief: dict[str, Any] | None = None,
    title: str = "",
) -> dict[str, Any]:
    """Build a visual-only production spec from a validated scenario.

    Derives the spatial map (environment, objects, props, actions) purely from
    the scenario's own visual content: the hypothesis title and summary reduced
    to filmable parts, locations named in events, participants and forensic
    spatial anchors. Deliberately excludes: evidence IDs, reports, witness
    statements, RAG context, similar cases, scores and reasoning text.
    """
    participants = [str(p).strip() for p in (scenario.participants or []) if str(p).strip()]

    locations: list[str] = []
    seen_loc: set[str] = set()
    for ev in events:
        loc = (ev.location or "").strip().title()
        if loc and loc not in seen_loc:
            seen_loc.add(loc)
            locations.append(loc)

    event_dicts = [
        {
            "description": ev.description,
            "event_type": ev.event_type,
            "timing": ev.timing or {},
            "location": ev.location or "",
        }
        for ev in events
    ]

    visual = brief or derive_visual_brief(
        summary=scenario.summary,
        title=title,
        participants=participants,
        events=event_dicts,
        locations=locations,
    )
    # A brief that names no actor while the scenario does is incomplete; keep the
    # structured participants rather than rendering an empty cast.
    actors = visual.get("actors") or [
        {"label": label, "appearance": DUMMY_APPEARANCE, "clothing": DUMMY_CLOTHING}
        for label in participants
    ]

    palette = ["#c85a5a", "#5a8ac8", "#6fbf6f", "#c8a85a"]
    characters = []
    for i, actor in enumerate(actors[:4]):
        label = str(actor.get("label") or f"Person {i + 1}")
        characters.append(
            {
                "id": f"char_{i + 1}",
                "label": label if len(label) <= 16 else f"Person {i + 1}",
                "appearance": str(actor.get("appearance") or DUMMY_APPEARANCE),
                "clothing": str(actor.get("clothing") or DUMMY_CLOTHING),
                "color": palette[i % len(palette)],
            }
        )

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

    # Time of day comes from the scenario's own event clocks, never a default.
    time_of_day, time_window = _clock_span(events)
    setting = str(visual.get("setting") or "").strip()
    if not setting:
        setting = ", ".join(locations[:6]) or "a single interior location"

    environment = {
        "type": "interior",
        "description": setting,
        "time_of_day": time_of_day,
        "time_window": time_window,
        "lighting": "neutral controlled lighting that follows the stated time of day",
    }

    return {
        "label": f"HYPOTHESIS {getattr(scenario, 'hypothesis_label', '') or '?'}",
        "title": scenario.summary[:200],
        "environment": environment,
        "characters": characters,
        "props": list(visual.get("props") or []),
        "beats": list(visual.get("beats") or []),
        "continuity": list(visual.get("continuity") or []),
        "absences": list(visual.get("absences") or []),
        # What the caps kept out of the brief. Reported to the operator; never
        # written into the prompt, where it would only invite the model to add it.
        "unshown": list(visual.get("unshown") or []),
        "objects": objects,
        "unknown_periods": [
            "EVENT NOT ESTABLISHED - no event is established for this period; leave it visually empty"
        ],
        "aspect_ratio": "16:9",
        "constraints": [
            "Do not add objects.",
            "Do not move objects to unsupported positions.",
            "Do not create unsupported actions or interactions.",
        ],
        "visual_only": True,
    }
