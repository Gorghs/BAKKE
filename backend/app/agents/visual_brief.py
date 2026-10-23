"""Visual brief: the scenario's own content reduced to what a camera can show.

The video director may not read case reports, evidence text or reasoning. This
module is the bridge. It keeps actors, props, actions and states, and drops
everything else. A real model can fill the brief, a deterministic extractor
fills it when the model is unavailable, and every model-filled brief passes a
containment gate before the director sees it.

The gate is the isolation guarantee: an actor or prop may only appear if its
name already appears in the scenario's own text, and an action may only appear
if it shares a verb with that text. A brief that invents a window, a lamp or a
second padlock is rejected and the deterministic brief is used instead.
"""

from __future__ import annotations

import json
import re
from typing import Any

# Words that never belong in a visual prompt because they carry reasoning,
# evaluation or forensic interpretation rather than visible content.
FORBIDDEN_TOKENS = (
    "witness",
    "similar case",
    "reference case",
    "hypothesis score",
    "evidence consistency",
    "rejection",
    "cause claim",
    "recommendation",
    "most likely",
    "suspect",
    "alibi",
    "motive",
    "guilt",
    "probability",
    "confidence",
    "score",
    "forensic",
    "autopsy",
    "post-mortem",
)

EVIDENCE_ID = re.compile(r"\bE-\d", re.IGNORECASE)
_UUID = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-", re.IGNORECASE)
_CLOCK = re.compile(r"\b(?:[01]?\d|2[0-3]):[0-5]\d\b")

# The user asked for an abstract figure, not a photoreal person: a dummy reads
# as "this is a reconstruction" on sight, which is what a hypothesis clip needs.
DUMMY_APPEARANCE = (
    "stylised dummy figure, smooth matte grey surface, featureless face with no eyes, "
    "nose or mouth, no hair, simplified rounded limbs, no skin texture"
)
DUMMY_CLOTHING = "plain dark grey coverall, no markings, no insignia"

_ABSENCE_PREFIXES = ("no ", "not ", "nothing ", "none ", "nobody ", "without ", "never ")
_ABSENCE_CUES = re.compile(
    r"\b(?:did not|does not|was not|were not|has not|have not|no recorded|not recorded|"
    r"not established|unrecorded)\b"
)

_STATE_WORDS = (
    "missing",
    "absent",
    "gone",
    "open",
    "closed",
    "locked",
    "unlocked",
    "empty",
    "broken",
    "damaged",
    "removed",
    "taken",
)
_STATE = re.compile(r"\b(" + "|".join(_STATE_WORDS) + r")\b", re.IGNORECASE)

# States that mean the object was there and is not any more. They share one
# phrasing in the prompt: one object at the start, none after the removal.
GONE_STATES = frozenset({"missing", "absent", "gone", "removed", "taken", "empty"})

# Verb forms the extractor accepts as an action a camera can follow. Anything
# outside this list is a state, a claim or reasoning, and is not animated.
_ACTION_FORMS = (
    "entered",
    "enters",
    "enter",
    "crossed",
    "crosses",
    "cross",
    "walked",
    "walks",
    "walk",
    "approached",
    "approaches",
    "approach",
    "removed",
    "removes",
    "remove",
    "opened",
    "opens",
    "open",
    "took",
    "takes",
    "take",
    "left",
    "leaves",
    "leave",
    "cut",
    "cuts",
    "climbed",
    "climbs",
    "climb",
    "forced",
    "forces",
    "force",
    "reached",
    "reaches",
    "reach",
    "carried",
    "carries",
    "carry",
    "placed",
    "places",
    "place",
    "unlocked",
    "unlocks",
    "locked",
    "locks",
    "broke",
    "breaks",
    "break",
    "ran",
    "runs",
    "run",
    "passed",
    "passes",
    "pass",
    "moved",
    "moves",
    "move",
    "lifted",
    "lifts",
    "lift",
    "pulled",
    "pulls",
    "pull",
    "pushed",
    "pushes",
    "push",
    "dropped",
    "drops",
    "drop",
    "hid",
    "hides",
    "hide",
    "returned",
    "returns",
    "return",
)
_ACTION_RE = re.compile(r"\b(" + "|".join(_ACTION_FORMS) + r")\b", re.IGNORECASE)

_PRESENT = {
    "entered": "enters",
    "enter": "enters",
    "crossed": "crosses",
    "cross": "crosses",
    "walked": "walks",
    "walk": "walks",
    "approached": "approaches",
    "approach": "approaches",
    "removed": "removes",
    "remove": "removes",
    "opened": "opens",
    "open": "opens",
    "took": "takes",
    "take": "takes",
    "left": "leaves",
    "leave": "leaves",
    "cut": "cuts",
    "climbed": "climbs",
    "climb": "climbs",
    "forced": "forces",
    "force": "forces",
    "reached": "reaches",
    "reach": "reaches",
    "carried": "carries",
    "carry": "carries",
    "placed": "places",
    "place": "places",
    "unlocked": "unlocks",
    "unlocks": "unlocks",
    "locked": "locks",
    "locks": "locks",
    "broke": "breaks",
    "break": "breaks",
    "ran": "runs",
    "run": "runs",
    "passed": "passes",
    "pass": "passes",
    "moved": "moves",
    "move": "moves",
    "lifted": "lifts",
    "lift": "lifts",
    "pulled": "pulls",
    "pull": "pulls",
    "pushed": "pushes",
    "push": "pushes",
    "dropped": "drops",
    "drop": "drops",
    "hid": "hides",
    "hide": "hides",
    "returned": "returns",
    "return": "returns",
}

# Actor nouns that can be lifted straight out of the scenario's own sentence.
# The qualifier is optional: a summary that says "A person crossed the yard" or
# "Person A entered" names an actor just as clearly as "an unknown person", and
# missing it left the clip with no cast and no action shots at all.
_ACTOR_NOUNS = r"(person|man|woman|figure|individual|visitor|intruder|occupant|worker|someone|somebody)"
_ACTOR_QUALIFIERS = (
    r"(unknown|unidentified|unseen|unrecognised|unrecognized|second|other|third)"
)
_ACTOR = re.compile(
    r"\b(?:(?:an?|the)\s+)?(?:" + _ACTOR_QUALIFIERS + r"\s+)?" + _ACTOR_NOUNS + r"\b",
    re.IGNORECASE,
)
_ACTOR_LETTER = re.compile(r"\bperson\s+([a-z])\b", re.IGNORECASE)

# Person nouns with no qualifier: "a visitor", "the figure". One such actor is
# the unidentified agent the scenario already has, so a second generic noun in
# the title does not add a second figure to the clip.
_PERSON_NOUNS = frozenset(
    {
        "person",
        "man",
        "woman",
        "figure",
        "individual",
        "visitor",
        "intruder",
        "occupant",
        "worker",
        "someone",
        "somebody",
    }
)


def _is_generic_person(label: str) -> bool:
    words = str(label or "").strip().lower().split()
    return bool(words) and words[-1] in _PERSON_NOUNS

# A verb that changes an object, followed by the object's own words. The object
# is read word by word rather than captured with one pattern: "opened the store
# door" names a two-word object, and a single-word capture produced "store".
_REMOVAL_VERB = re.compile(
    r"\b(removed|removes|remove|took|takes|take|opened|opens|open|cut|cuts|broke|breaks|"
    r"forced|forces|force|unlocked|unlocks|locked|locks|lifted|lifts|lift)\b"
    r"\s+(?:the|a|an)\s+",
    re.IGNORECASE,
)

# What a change verb leaves the object in. A removal leaves the object gone; an
# opener leaves the door open. Mapping every verb to "missing" turned "opened
# the store door" into "no store door is in frame".
_VERB_END_STATE = {
    "remove": "missing",
    "take": "missing",
    "lift": "missing",
    "open": "open",
    "unlock": "unlocked",
    "lock": "locked",
    "cut": "damaged",
    "break": "damaged",
    "force": "damaged",
}

_OBJECT_STOP = frozenset(
    {
        "from",
        "at",
        "in",
        "on",
        "onto",
        "into",
        "to",
        "with",
        "by",
        "near",
        "outside",
        "inside",
        "over",
        "under",
        "behind",
        "across",
        "through",
        "against",
        "until",
        "within",
        "before",
        "after",
        "during",
        "while",
        "when",
        "which",
        "that",
        "and",
        "then",
    }
)

_STOP = frozenset(
    {
        "the",
        "and",
        "with",
        "from",
        "that",
        "this",
        "into",
        "over",
        "after",
        "before",
        "then",
        "when",
        "while",
        "their",
        "there",
        "which",
        "were",
        "was",
        "has",
        "have",
        "had",
        "for",
        "not",
        "but",
        "his",
        "her",
        "its",
        "are",
        "been",
        "being",
        "they",
        "them",
        "onto",
        "near",
        "across",
        "between",
        "during",
        "around",
        "through",
        "against",
        "until",
        "within",
        "outside",
        "inside",
    }
)


def _stem(word: str) -> str:
    for suffix in ("ing", "ies", "ied", "ed", "es", "s"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            base = word[: -len(suffix)]
            return base + "y" if suffix == "ies" else base
    return word


def _stems(text: str) -> set[str]:
    return {
        _stem(word)
        for word in re.findall(r"[a-z]{3,}", (text or "").lower())
        if word not in _STOP
    }


def _similar(first: str, second: str) -> bool:
    """True when two lines say roughly the same thing.

    Used to drop a deterministic continuity line that the model already
    phrased, so the prompt does not state the same rule twice.
    """
    a, b = _stems(first), _stems(second)
    if not a or not b:
        return False
    return len(a & b) / min(len(a), len(b)) >= 0.5


def present_tense(action: str) -> str:
    """Rewrite the action verbs into present tense, which shot lists read better."""

    def swap(match: re.Match[str]) -> str:
        return _PRESENT.get(match.group(1).lower(), match.group(1))

    return _ACTION_RE.sub(swap, action or "")


def _end_state_for(verb: str) -> str:
    """The state a change verb leaves its object in, or "" when it changes none."""
    present = _PRESENT.get(verb.lower(), verb.lower())
    base = present[:-1] if present.endswith("s") else present
    return _VERB_END_STATE.get(base, "")


def _object_phrase(text: str) -> str:
    """The object named after a change verb, cut at the first qualifier.

    Runs of one to three words are kept so "store door" survives whole, and the
    phrase stops at a preposition or a state word so "the padlock from the store
    door" yields "padlock".
    """
    words: list[str] = []
    for token in re.findall(r"[a-z][a-z\-]*", (text or "").lower()):
        if token in _OBJECT_STOP or token in _STATE_WORDS:
            break
        words.append(token)
        if len(words) == 3:
            break
    return " ".join(words)


def is_absence(description: str) -> bool:
    low = (description or "").strip().lower()
    if not low:
        return False
    if low.startswith(_ABSENCE_PREFIXES):
        return True
    return bool(_ABSENCE_CUES.search(low))


def _clock_from(text: str) -> str:
    match = _CLOCK.search(text or "")
    return match.group(0) if match else ""


def _timing_clocks(timing: Any) -> list[str]:
    if not isinstance(timing, dict):
        return []
    found: list[str] = []
    for key in ("start", "end", "time", "period", "window", "from", "to"):
        raw = timing.get(key)
        if raw in (None, ""):
            continue
        for part in re.split(r"\s*(?:-|–|—|to|until)\s*", str(raw).strip()):
            if _CLOCK.fullmatch(part.strip()) and part.strip() not in found:
                found.append(part.strip())
    return found


def _clauses(text: str) -> list[str]:
    """Split a summary into the clauses that could each be one beat.

    Commas separate actions as often as "and" does ("the figure entered the
    yard, crossed to the door, removed the padlock"), so they split too. A
    clause with no action verb is dropped by the caller.
    """
    parts = re.split(r";|,\s*(?:and|then)\s+|,|\s+and\s+|\s+then\s+|\.\s+", text or "")
    return [p.strip(" .") for p in parts if p and p.strip(" .")]


def _actor_in(text: str, actors: list[dict[str, Any]]) -> str:
    low = (text or "").lower()
    for actor in actors:
        label = str(actor.get("label", "")).lower()
        if label and label in low:
            return actor["label"]
    for actor in actors:
        words = [w for w in str(actor.get("label", "")).lower().split() if len(w) > 2]
        if words and all(word in low for word in words[:1]):
            return actor["label"]
    return ""


def _actors(participants: list[str], summary: str, title: str) -> list[dict[str, Any]]:
    labels: list[str] = []
    for raw in participants or []:
        label = str(raw).strip()
        if label and label.lower() not in {x.lower() for x in labels}:
            labels.append(label)
    for text in (summary, title):
        for match in _ACTOR.finditer(text or ""):
            qualifier = (match.group(1) or "").strip()
            noun = match.group(2).lower()
            letter = _ACTOR_LETTER.match((text or "")[match.start() :])
            if letter:
                label = f"{noun.capitalize()} {letter.group(1).upper()}"
            elif qualifier:
                label = f"{qualifier.capitalize()} {noun}"
            else:
                label = noun.capitalize()
            if label.lower() in {x.lower() for x in labels}:
                continue
            if any(noun in existing.lower() for existing in labels):
                continue
            if not qualifier and not letter and any(_is_generic_person(x) for x in labels):
                continue
            labels.append(label)
    return [
        {"label": label[:40], "appearance": DUMMY_APPEARANCE, "clothing": DUMMY_CLOTHING}
        for label in labels[:3]
    ]


def _prop_label(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def _props(
    events: list[dict[str, Any]],
    summary: str,
    title: str,
    locations: list[str],
) -> tuple[list[dict[str, Any]], list[str]]:
    """Objects that change state, plus the labels dropped for want of room.

    A location is not a prop: it is the space itself, so a label that names one
    of the scenario's own locations stays out. Whatever the cap drops is
    returned so the caller can report it instead of losing it silently.
    """
    props: dict[str, dict[str, Any]] = {}
    dropped: list[str] = []
    blocked = {loc.lower() for loc in locations}

    def add(label: str, state: str, where: str, removal: bool) -> None:
        label = _prop_label(label)
        if not label or label in blocked:
            return
        if label not in props and len(props) >= 4:
            if label not in dropped:
                dropped.append(label)
            return
        entry = props.setdefault(
            label,
            {"label": label, "start_state": "", "end_state": "", "location": ""},
        )
        if state and not entry["end_state"]:
            entry["end_state"] = state.lower()
        if where and not entry["location"]:
            entry["location"] = where
        if removal:
            entry["start_state"] = "present"

    def read_change(desc: str, where: str) -> None:
        for match in _REMOVAL_VERB.finditer(desc or ""):
            label = _object_phrase(desc[match.end() :])
            if label:
                add(label, _end_state_for(match.group(1)), where, True)

    for event in events:
        desc = str(event.get("description") or "").strip()
        where = str(event.get("location") or "").strip().lower()
        if not desc:
            continue
        match = re.match(
            r"^(?:the\s+|a\s+|an\s+)?([a-z][a-z\-]*(?:\s+[a-z][a-z\-]*)?)\s+"
            r"(?:is\s+|was\s+|are\s+|were\s+)?(" + "|".join(_STATE_WORDS) + r")\b",
            desc.lower(),
        )
        if match:
            add(match.group(1), match.group(2), where, match.group(2).lower() in GONE_STATES)
        read_change(desc, where)

    for text in (summary, title):
        read_change(text or "", "")
        for match in re.finditer(
            r"\b([a-z][a-z\-]{2,24})\s+(?:was|is|were|are)\s+(" + "|".join(_STATE_WORDS) + r")\b",
            (text or "").lower(),
        ):
            add(match.group(1), match.group(2), "", match.group(2).lower() in GONE_STATES)
    return list(props.values()), dropped


def _beats(
    events: list[dict[str, Any]],
    summary: str,
    title: str,
    actors: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    """One beat per action the scenario states, and the actions left unscheduled.

    An action needs a figure to perform it. Without a named actor the beat is
    not animated, because a self-moving prop is exactly the nonsense this
    pipeline is meant to avoid, so it comes back as a report instead.
    """
    beats: list[dict[str, Any]] = []
    dropped: list[str] = []

    def push(clock: str, actor: str, action: str, source: str = "") -> None:
        action = re.sub(r"\s+", " ", action).strip(" .,")
        if not action or len(action) > 200:
            if action:
                dropped.append(action[:120])
            return
        if not actor:
            # Without a figure the beat would be a prop moving on its own. The
            # whole clause is reported, because the action keeps only the words
            # from the verb onwards.
            dropped.append(re.sub(r"\s+", " ", (source or action)).strip()[:120])
            return
        if any(
            _stem(action.split()[0]) == _stem(b["action"].split()[0])
            and action.lower() == b["action"].lower()
            for b in beats
        ):
            return
        if len(beats) >= 4:
            dropped.append(action[:120])
            return
        beats.append({"clock": clock, "actor": actor, "action": action})

    fallback_actor = actors[0]["label"] if actors else ""

    for event in events:
        desc = str(event.get("description") or "").strip()
        if not desc or is_absence(desc):
            continue
        match = _ACTION_RE.search(desc)
        if not match:
            continue
        action = desc[match.start() :]
        clock = _clock_from(desc) or (_timing_clocks(event.get("timing")) or [""])[0]
        push(clock, _actor_in(desc, actors) or fallback_actor, action, desc)

    for clause in _clauses(summary):
        if is_absence(clause):
            continue
        match = _ACTION_RE.search(clause)
        if not match:
            continue
        action = clause[match.start() :]
        actor = _actor_in(clause, actors)
        if not actor and beats:
            actor = beats[-1]["actor"]
        push(_clock_from(clause), actor or fallback_actor, action, clause)
    return beats, dropped


def _absences(events: list[dict[str, Any]]) -> list[str]:
    """Nouns the scenario says were *not* there.

    They stay out of the visual body, where naming them invites the model to
    draw them, and become exclusions in the constraints section instead.
    """
    nouns: list[str] = []
    for event in events:
        desc = str(event.get("description") or "").strip()
        match = re.match(r"^no(?:ne)?\s+(?:recorded\s+)?([a-z][a-z\-]{2,24})\b", desc, re.I)
        if match:
            noun = match.group(1).lower()
            if noun not in nouns:
                nouns.append(noun)
    return nouns[:4]


def _continuity(
    events: list[dict[str, Any]],
    beats: list[dict[str, Any]],
    props: list[dict[str, Any]],
) -> list[str]:
    lines: list[str] = []
    for event in events:
        desc = str(event.get("description") or "").strip()
        if not desc:
            continue
        if is_absence(desc):
            lines.append(
                "The space stays empty around the action; nothing else enters, crosses or "
                "leaves the frame."
            )
        elif not _ACTION_RE.search(desc) and not _STATE.search(desc):
            lines.append(f"The space holds in this state: {desc.rstrip('.')}.")
    if beats:
        lines.append("The action happens once, in this order; nothing repeats and nothing loops.")
    for prop in props:
        if prop.get("end_state") in GONE_STATES:
            lines.append(
                f"The {prop['label']} is present at the start and gone after it is removed. "
                "It never appears twice, and it never moves on its own."
            )
    seen: list[str] = []
    for line in lines:
        if line not in seen:
            seen.append(line)
    return seen[:6]


def _setting(locations: list[str]) -> str:
    if not locations:
        return ""
    if len(locations) == 1:
        return f"the {locations[0].lower()}"
    return "the " + " and the ".join(loc.lower() for loc in locations[:3])


def derive_visual_brief(
    *,
    summary: str = "",
    title: str = "",
    participants: list[str] | None = None,
    events: list[dict[str, Any]] | None = None,
    locations: list[str] | None = None,
) -> dict[str, Any]:
    """Build a visual-only brief from the scenario's own structured content.

    No model, no parser guesswork: actors come from `participants` plus an
    explicit "unknown person" phrase, props from state and removal phrasings,
    beats from clauses that contain a camera-followable verb. Anything that is
    not visible stays out.
    """
    event_rows = events or []
    locations = [loc for loc in (locations or []) if loc]
    actors = _actors(participants or [], summary, title)
    props, dropped_props = _props(event_rows, summary, title, locations)
    beats, dropped_beats = _beats(event_rows, summary, title, actors)
    unshown = [f"Object not shown, over the four-object limit: {label}" for label in dropped_props]
    unshown += [f"Action not animated: {action}" for action in dropped_beats]
    return {
        "setting": _setting(locations),
        "actors": actors,
        "props": props,
        "beats": beats,
        "continuity": _continuity(event_rows, beats, props),
        "absences": _absences(event_rows),
        "unshown": unshown[:8],
    }


def _as_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return " ".join(_as_text(v) for v in value)
    if isinstance(value, dict):
        return " ".join(_as_text(v) for v in value.values())
    return ""


def source_text(payload: dict[str, Any]) -> str:
    return _as_text(payload)


def brief_problem(brief: Any, source: str) -> str:
    """Return the reason a model-filled brief cannot be trusted, or "".

    Containment is the point: a label or an action word that the scenario never
    states is an invention, and the previous rewrite invented a window, a lamp
    and a prior padlock state. A clock the scenario never states is an invented
    time of day. A brief that fails any check is dropped whole and the
    deterministic brief is used instead.
    """
    if not isinstance(brief, dict):
        return "brief: not an object"
    if len(json.dumps(brief, default=str)) > 3000:
        return "brief: too long"
    for key in ("setting", "actors", "props", "beats", "continuity"):
        if key not in brief:
            return f"brief: missing '{key}'"
    if not isinstance(brief.get("actors"), list) or len(brief["actors"]) > 3:
        return "brief: actors must be a list of at most 3"
    if not isinstance(brief.get("props"), list) or len(brief["props"]) > 4:
        return "brief: props must be a list of at most 4"
    if not isinstance(brief.get("beats"), list) or len(brief["beats"]) > 5:
        return "brief: beats must be a list of at most 5"
    if not isinstance(brief.get("continuity"), list) or len(brief["continuity"]) > 6:
        return "brief: continuity must be a list of at most 6"

    blob = json.dumps(brief, default=str)
    low = blob.lower()
    for token in FORBIDDEN_TOKENS:
        if token in low:
            return f"brief: forbidden token '{token}'"
    if EVIDENCE_ID.search(blob):
        return "brief: evidence id"
    if _UUID.search(blob):
        return "brief: internal identifier"

    if not isinstance(brief.get("setting", ""), str) or len(brief.get("setting", "")) > 200:
        return "brief: setting must be a string of at most 200 chars"

    stems = _stems(source)
    # Containment, not overlap. Sharing one word with the scenario proves
    # nothing: "store window" shares "store" with a scenario that only ever says
    # "store", and an overlap test let that invention through. Every content word
    # in a label must already appear in the scenario's own text.
    setting_stems = _stems(str(brief.get("setting") or ""))
    if setting_stems and not setting_stems <= stems:
        return f"brief: setting '{brief.get('setting')}' is not named in the scenario"

    # A clock the scenario never states is an invented time of day, and the
    # visual prompt prints a beat clock verbatim.
    source_clocks = set(_CLOCK.findall(source))
    for clock in _CLOCK.findall(blob):
        if clock not in source_clocks:
            return f"brief: clock '{clock}' is not a time the scenario states"

    for actor in brief["actors"]:
        if not isinstance(actor, dict):
            return "brief: actor must be an object"
        label = str(actor.get("label") or "").strip()
        if not label or len(label) > 40:
            return "brief: actor label missing or too long"
        if not _stems(label) <= stems:
            return f"brief: actor '{label}' is not named in the scenario"
        for field in ("appearance", "clothing"):
            if len(str(actor.get(field) or "")) > 200:
                return f"brief: actor {field} too long"

    for prop in brief["props"]:
        if not isinstance(prop, dict):
            return "brief: prop must be an object"
        label = str(prop.get("label") or "").strip()
        if not label or len(label) > 40:
            return "brief: prop label missing or too long"
        if not _stems(label) <= stems:
            return f"brief: prop '{label}' is not named in the scenario"
        for field in ("start_state", "end_state", "location"):
            if len(str(prop.get(field) or "")) > 120:
                return f"brief: prop {field} too long"

    for beat in brief["beats"]:
        if not isinstance(beat, dict):
            return "brief: beat must be an object"
        action = str(beat.get("action") or "").strip()
        if not action or len(action) > 220:
            return "brief: beat action missing or too long"
        if not _stems(action) <= stems:
            return f"brief: action '{action[:60]}' is not stated in the scenario"
        if len(str(beat.get("clock") or "")) > 20:
            return "brief: beat clock too long"

    for line in brief["continuity"]:
        if not isinstance(line, str) or len(line) > 220:
            return "brief: continuity line missing or too long"

    absences = brief.get("absences", [])
    if not isinstance(absences, list) or len(absences) > 4:
        return "brief: absences must be a list of at most 4"
    for noun in absences:
        if not isinstance(noun, str) or not noun.strip() or len(noun) > 30:
            return "brief: absence noun missing or too long"
        if not _stems(noun) <= stems:
            return f"brief: absence '{noun}' is not named in the scenario"
    return ""


def brief_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """The deterministic brief for one task payload."""
    events = [e for e in (payload.get("events") or []) if isinstance(e, dict)]
    return derive_visual_brief(
        summary=str(payload.get("scenario_summary") or ""),
        title=str(payload.get("hypothesis_title") or ""),
        participants=[str(p) for p in (payload.get("participants") or [])],
        events=events,
        locations=[str(e.get("location") or "") for e in events if e.get("location")],
    )


def merge_briefs(brief: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any]:
    """Keep the model's wording, but never lose something the scenario states.

    A model brief can pass the gate and still be incomplete: it may merge two
    actions into one beat, or drop the object that changes state. Coverage is
    checked per item against the deterministic brief, which is derived from the
    scenario alone, and anything missing is restored in place.
    """
    merged = dict(brief)

    actors = list(brief.get("actors") or [])
    for actor in fallback.get("actors") or []:
        if not any(_stems(actor["label"]) & _stems(existing["label"]) for existing in actors):
            actors.append(actor)
    if actors:
        merged["actors"] = actors[:3]

    props = list(brief.get("props") or [])
    for prop in fallback.get("props") or []:
        if not any(_stems(prop["label"]) & _stems(existing["label"]) for existing in props):
            props.append(prop)
    if props:
        merged["props"] = props[:4]

    beats = list(brief.get("beats") or [])
    for base in fallback.get("beats") or []:
        base_stems = _stems(base.get("action", ""))
        if any(_stems(beat.get("action", "")) & base_stems for beat in beats):
            continue
        beats.append(base)
    merged["beats"] = beats[:5]

    absences = list(brief.get("absences") or [])
    for noun in fallback.get("absences") or []:
        if noun not in absences:
            absences.append(noun)
    merged["absences"] = absences[:4]

    # Continuity is a rule set, not description. The deterministic brief already
    # derives every rule the scenario supports, so a model line that restates one
    # of them adds nothing and a line that does not adds a rule the scenario never
    # implies (the previous rewrite invented a prior padlock state this way).
    merged["continuity"] = list(fallback.get("continuity") or [])[:6]

    # What the caps kept out of the brief is the operator's report, never model
    # output, so it always comes from the deterministic brief.
    merged["unshown"] = list(fallback.get("unshown") or [])

    if not str(merged.get("setting") or "").strip():
        merged["setting"] = fallback.get("setting", "")
    else:
        # A setting that drops one of the scenario's own areas hides where the
        # action happens; the deterministic setting names all of them.
        fallback_setting = str(fallback.get("setting") or "")
        if fallback_setting and not (_stems(fallback_setting) <= _stems(str(merged["setting"]))):
            merged["setting"] = fallback_setting
    return merged


def request_visual_brief(payload: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Ask the model for a brief and keep it only if it passes the gate.

    A rejected or failed brief returns None. The caller then uses the
    deterministic brief, so a provider outage never blocks a render and never
    widens what reaches the video model.
    """
    meta: dict[str, Any] = {"provider": "", "is_mock": False, "used": False, "reason": ""}
    source = source_text(payload)
    if not source.strip():
        meta["reason"] = "brief: nothing to describe"
        return None, meta
    from app.providers.registry import get_llm_provider

    try:
        llm = get_llm_provider()
        meta["provider"] = llm.name
        meta["is_mock"] = bool(getattr(llm, "is_mock", False))
        out = llm.run_task("build_visual_brief", payload)
        problem = brief_problem(out, source)
        if problem:
            meta["reason"] = problem
            return None, meta
        merged = merge_briefs(out, brief_from_payload(payload))
        problem = brief_problem(merged, source)
        if problem:
            meta["reason"] = problem
            return None, meta
        meta["used"] = True
        return merged, meta
    except Exception as exc:  # noqa: BLE001
        meta["reason"] = f"brief failed: {exc}"[:300]
        return None, meta
