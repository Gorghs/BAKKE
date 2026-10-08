"""Deterministic, rule-based implementations backing the DEVELOPMENT MOCK AI
providers. These make the full pipeline runnable without external API keys
while the architecture keeps the same contracts as real providers.

Every mock output is explicitly labelled "DEVELOPMENT MOCK" downstream and is
NEVER presented as a real AI result.
"""
from __future__ import annotations

import re
from typing import Any

from app.config import get_settings

settings = get_settings()

TIME_RE = re.compile(r"\b(\d{1,2}:\d{2})\s*(?:–|-|to)\s*(\d{1,2}:\d{2})\b|\b(\d{1,2}:\d{2})\b")
PERSON_RE = re.compile(r"\bPerson\s+([A-Z])\b")
TIME_QUALIFIERS = ["approximately", "around", "approx", "estimated", "about", "~"]
STRONG_QUALIFIERS = ["confirmed", "observed", "measured", "verified", "recorded", "reported"]
WEAK_QUALIFIERS = [
    "possible",
    "possibly",
    "suspected",
    "maybe",
    "uncertain",
    "inconclusive",
    "unknown",
    "cannot determine",
    "could not determine",
    "not established",
]

PERSON_NAMES = {
    "victim",
    "citizen",
    "deceased",
    "suspect",
    "witness",
    "complainant",
    "caller",
    "neighbour",
    "neighbor",
}

LOCATIONS = [
    "hallway",
    "hall",
    "room",
    "kitchen",
    "bedroom",
    "bathroom",
    "living room",
    "garage",
    "garden",
    "alley",
    "street",
    "warehouse",
    "corridor",
    "stairwell",
    "basement",
    "office",
    "car park",
    "parking lot",
    "building",
    "premises",
]

PERSONS = [
    "person a",
    "person b",
    "person c",
    "person d",
    "victim",
    "suspect",
    "perpetrator",
    "attacker",
    "suspect a",
    "suspect b",
]

OBJECTS = [
    "knife",
    "weapon",
    "gun",
    "firearm",
    "bottle",
    "rope",
    "phone",
    "mobile",
    "hammer",
    "screwdriver",
    "scissors",
    "blade",
    "glass shard",
]

BODY_PARTS = [
    "right hip",
    "left hip",
    "hip",
    "chest",
    "thorax",
    "abdomen",
    "head",
    "skull",
    "neck",
    "right arm",
    "left arm",
    "right leg",
    "left leg",
    "right hand",
    "left hand",
    "right shoulder",
    "left shoulder",
    "back",
    "face",
]

ACTIONS = [
    "entered",
    "exited",
    "left",
    "arrived",
    "departed",
    "moved",
    "was seen",
    "was observed",
    "carrying",
    "holding",
    "armed with",
    "fled",
    "ran",
]

COVERAGE_PHRASES = [
    "no camera coverage",
    "not covered by camera",
    "not covered by cctv",
    "no cctv coverage",
    "blind spot",
    "camera blind",
    "no coverage",
    "no surveillance",
    "covered by cctv",
    "covered by camera",
    "camera coverage",
    "hallway coverage",
]

CONFLICT_PHRASES = [
    "conflicts with",
    "contradicts",
    "disagrees with",
    "inconsistent with",
    "does not match",
]


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def _detect_times(sentence: str) -> tuple[str, str, str, str]:
    """Return (time_type, start, end, label)."""
    m = TIME_RE.search(sentence)
    if not m:
        return "UNKNOWN", "", "", ""
    if m.group(1) and m.group(2):
        return "INTERVAL", m.group(1), m.group(2), f"{m.group(1)}–{m.group(2)}"
    t = m.group(3)
    qual = "APPROXIMATE" if any(q in _norm(sentence) for q in TIME_QUALIFIERS) else "EXACT"
    return qual, t, "", t


def _qualifier(sentence: str) -> tuple[str, str, str]:
    """Return (qualifier, status, constraint_strength)."""
    n = _norm(sentence)
    for w in WEAK_QUALIFIERS:
        if w in n:
            return w, "BOUNDED" if "estimated" in w or "approximately" in w else "SOFT", "SOFT"
    for w in STRONG_QUALIFIERS:
        if w in n:
            return w, "HARD", "HARD"
    return "reported", "HARD", "SOFT"


def _detect_injury(sentence: str) -> dict[str, Any] | None:
    n = _norm(sentence)
    for part in BODY_PARTS:
        if part in n and ("injur" in n or "wound" in n or "laceration" in n or "fracture" in n or "stab" in n):
            return {"injury_location": part, "sentence": sentence}
    return None


def _detect_coverage(sentence: str) -> dict[str, Any] | None:
    n = _norm(sentence)
    for phrase in COVERAGE_PHRASES:
        if phrase in n:
            return {"phrase": phrase, "sentence": sentence}
    return None


def _detect_spatial(sentence: str, evidence_type: str) -> dict[str, Any] | None:
    """Detect 'person at location at time' claims -> metadata['spatial']."""
    n = _norm(sentence)
    times = TIME_RE.findall(sentence)
    time_tokens: list[str] = []
    for g in times:
        time_tokens.extend(t for t in g if t)
    person = None
    m = PERSON_RE.search(sentence)
    if m:
        person = f"Person {m.group(1)}"
    else:
        for nm in PERSON_NAMES:
            if nm in n:
                person = nm.title()
                break
    location = None
    for loc in LOCATIONS:
        if loc in n:
            location = loc.title()
            break
    if person and location and time_tokens:
        return {"person": person, "location": location, "time": time_tokens[0], "source_type": evidence_type}
    return None


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def mock_extract(payload: dict[str, Any]) -> dict[str, Any]:
    """Rule-based evidence extraction used by the mock LLM provider."""
    text = payload.get("text", "")
    evidence_type = payload.get("evidence_type", "TEXT")
    evidence_id = payload.get("evidence_id", "E-001")

    facts: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    entities: list[dict[str, Any]] = []
    timeline_events: list[dict[str, Any]] = []
    entity_map: dict[str, str] = {}

    def _add_entity(name: str, etype: str, desc: str = "") -> None:
        key = (name.lower(), etype)
        if key not in entity_map:
            entity_map[key] = name
            entities.append({"name": name, "entity_type": etype, "description": desc, "metadata": {}})

    sentences = _split_sentences(text)
    for idx, sentence in enumerate(sentences):
        n = _norm(sentence)
        qual, status, strength = _qualifier(sentence)
        time_type, t_start, t_end, t_label = _detect_times(sentence)

        is_authoritative = evidence_type in ("FORENSIC_REPORT", "POST_MORTEM_REPORT")
        if evidence_type == "WITNESS_STATEMENT" and any(c in n for c in CONFLICT_PHRASES):
            status = "CONTESTED"

        fact: dict[str, Any] = {
            "statement": sentence,
            "status": status,
            "constraint_strength": strength if is_authoritative else "SOFT",
            "category": "GENERAL",
            "qualifier": qual,
            "source_evidence_ids": [evidence_id],
            "source_refs": [{"evidence_id": evidence_id, "paragraph_index": idx, "section": "", "note": "sentence"}],
            "is_authoritative": is_authoritative,
            "metadata": {},
        }

        # entity detection
        for m in PERSON_RE.finditer(sentence):
            _add_entity(f"Person {m.group(1)}", "PERSON")
        for nm in PERSON_NAMES:
            if nm in n:
                _add_entity(nm.title(), "PERSON")
        for loc in LOCATIONS:
            if loc in n:
                _add_entity(loc.title(), "LOCATION", "detected location")
        for obj in OBJECTS:
            if obj in n:
                _add_entity(obj.title(), "OBJECT", "detected object")

        inj = _detect_injury(sentence)
        if inj:
            part = inj["injury_location"]
            fact["category"] = "FORENSIC" if evidence_type in ("FORENSIC_REPORT", "POST_MORTEM_REPORT") else "GENERAL"
            fact["metadata"]["injury_location"] = part
            if is_authoritative:
                fact["constraint_strength"] = "HARD"
                findings.append(
                    {
                        "category": "POST_MORTEM" if evidence_type == "POST_MORTEM_REPORT" else "FORENSIC",
                        "title": f"Injury location: {part}",
                        "summary": f"The report states the injury is located at the {part}.",
                        "details": {"injury_location": part},
                        "strength": "HARD",
                        "status": "AUTHORITATIVE_SOURCE_FINDING",
                        "source_evidence_ids": [evidence_id],
                    }
                )

        cov = _detect_coverage(sentence)
        if cov:
            fact["metadata"]["coverage"] = cov["phrase"]
            fact["category"] = "SPATIAL"
            if any(neg in cov["phrase"] for neg in ("no ", "blind", "not covered")):
                fact["metadata"]["camera_coverage"] = "NO_COVERAGE"
            else:
                fact["metadata"]["camera_coverage"] = "KNOWN_COVERED"

        spatial = _detect_spatial(sentence, evidence_type)
        if spatial:
            fact["metadata"]["spatial"] = spatial
            fact["category"] = "SPATIAL"

        if evidence_type == "POST_MORTEM_REPORT" and ("cause" in n and "death" in n):
            fact["category"] = "POST_MORTEM"
            findings.append(
                {
                    "category": "POST_MORTEM",
                    "title": "Cause of death statement",
                    "summary": sentence,
                    "details": {"sentence": sentence},
                    "strength": "SOFT" if qual in WEAK_QUALIFIERS else "HARD",
                    "status": "SOURCE_REPORTED",
                    "source_evidence_ids": [evidence_id],
                }
            )

        fact["metadata"]["evidence_type"] = evidence_type
        facts.append(fact)

        if time_type != "UNKNOWN":
            timeline_events.append(
                {
                    "title": sentence[:80],
                    "description": sentence,
                    "time_type": time_type,
                    "time_start": t_start,
                    "time_end": t_end,
                    "time_label": t_label,
                    "certainty": "BOUNDED" if time_type == "APPROXIMATE" else "KNOWN",
                    "ordering_index": idx,
                    "linked_fact_ids": [fact["fact_id"]] if "fact_id" in fact else [],
                    "source_evidence_ids": [evidence_id],
                }
            )

    # Build evidence-type-specific summary findings.
    if evidence_type == "WITNESS_STATEMENT":
        findings.append(
            {
                "category": "WITNESS",
                "title": "Witness statement",
                "summary": text[:1500],
                "details": {"sentence_count": len(sentences)},
                "strength": "SOFT",
                "status": "SOURCE_REPORTED",
                "source_evidence_ids": [evidence_id],
            }
        )

    return {
        "facts": facts,
        "findings": findings,
        "entities": entities,
        "timeline_events": timeline_events,
        "provider": "mock",
    }


def _facts_summary(facts: list[dict[str, Any]]) -> dict[str, Any]:
    persons: list[str] = []
    objects: list[str] = []
    locations: list[str] = []
    injury: str | None = None
    has_knife = False
    has_entry = False
    has_exit = False
    blind_locations: list[str] = []
    coverage_known: list[str] = []
    for f in facts:
        meta = f.get("metadata", {})
        if meta.get("injury_location"):
            injury = meta["injury_location"]
        if meta.get("camera_coverage") == "NO_COVERAGE":
            blind_locations.append("unknown")
        if meta.get("camera_coverage") == "KNOWN_COVERED":
            coverage_known.append("known")
        n = _norm(f.get("statement", ""))
        if meta.get("person"):
            p = meta["person"]
            if p not in persons:
                persons.append(p)
        else:
            for p in PERSONS:
                if p in n and p not in persons:
                    persons.append(p)
        for obj in OBJECTS:
            if obj in n:
                objects.append(obj.title())
                if obj == "knife":
                    has_knife = True
        for loc in LOCATIONS:
            if loc in n and loc.title() not in locations:
                locations.append(loc.title())
        if "entered" in n or "arrived" in n:
            has_entry = True
        if "exited" in n or "left" in n or "departed" in n:
            has_exit = True
    return {
        "persons": persons,
        "objects": objects,
        "locations": locations,
        "injury": injury,
        "has_knife": has_knife,
        "has_entry": has_entry,
        "has_exit": has_exit,
        "blind_count": len(blind_locations),
        "covered_count": len(coverage_known),
    }


def _timeline_brief(timeline: list[dict[str, Any]]) -> list[str]:
    out = []
    for t in timeline:
        label = t.get("time_label") or f"{t.get('time_start')}-{t.get('time_end')}"
        out.append(f"[{t.get('certainty', 'KNOWN')} {label}] {t.get('description', '')[:120]}")
    return out


def _make_scenario_events(summary: dict[str, Any], timeline: list[dict[str, Any]], kind: str) -> list[dict[str, Any]]:
    """Build a scenario event sequence from known timeline + inferred/unknown parts."""
    events: list[dict[str, Any]] = []
    order = 0
    for t in timeline:
        events.append(
            {
                "description": t.get("description", ""),
                "event_type": "KNOWN" if t.get("certainty") == "KNOWN" else "BOUNDED",
                "linked_fact_ids": t.get("linked_fact_ids", []),
                "evidence_links": t.get("source_evidence_ids", []),
                "timing": {"time_type": t.get("time_type"), "start": t.get("time_start"), "end": t.get("time_end")},
                "location": "",
            }
        )
        order += 1
    return events


def mock_generate_hypotheses(payload: dict[str, Any]) -> dict[str, Any]:
    facts = payload.get("facts", [])
    if not facts:
        # No evidence, no hypotheses. BAKKE never fabricates scenarios.
        return {"hypotheses": [], "provider": "mock", "note": "no evidence extracted"}
    timeline = payload.get("timeline", [])
    anchors = payload.get("anchors", [])
    similar_cases = payload.get("similar_cases", [])
    summary = _facts_summary(facts)
    injury = summary["injury"]
    persons = summary["persons"]

    anchor_value = None
    for a in anchors:
        if a.get("type") == "INJURY_LOCATION":
            anchor_value = a.get("value", {}).get("location")

    candidates: list[dict[str, Any]] = []

    def _add(title, cause_claim, participants, events, unknowns, origin="INITIAL", patterns=None, injury_loc=""):
        candidates.append(
            {
                "title": title,
                "summary": title,
                "cause_claim": cause_claim,
                "participants": participants,
                "events": events,
                "unknowns": unknowns,
                "origin": origin,
                "similar_case_patterns_used": patterns or [],
                "injury_location": injury_loc or "",
            }
        )

    unknown_events = (
        ["Events inside the blind / unobserved area are not established."]
        if summary["blind_count"] > 0 or summary["covered_count"] == 0
        else ["The causal sequence is not established by the available evidence."]
    )

    base_events = _make_scenario_events(summary, timeline, "base")
    knife_note = summary["has_knife"]

    # 1. Person-caused (presence-consistent) scenarios
    for person in persons:
        _add(
            f"{person} performed an action consistent with causing the injury",
            f"{person} caused the injury",
            [person],
            base_events + [{"description": f"Injury to {injury} occurred during this sequence.", "event_type": "INFERRED", "linked_fact_ids": [], "evidence_links": [], "timing": {}, "location": ""}],
            unknown_events,
            patterns=["similar injury pattern"] if similar_cases else [],
            injury_loc=injury,
        )

    # 2. Self-inflicted
    _add(
        "The injury may have been self-inflicted",
        "the injury was self-inflicted",
        persons + ["Victim"],
        base_events + [{"description": "The injury was self-inflicted.", "event_type": "INFERRED", "linked_fact_ids": [], "evidence_links": [], "timing": {}, "location": ""}],
        unknown_events,
        injury_loc=injury,
    )

    # 3. Interaction with unestablished causation
    _add(
        "An interaction occurred but causation is not established",
        "interaction occurred; causation not established",
        persons,
        base_events + [{"description": "An interaction occurred, but the available evidence does not establish who caused the injury.", "event_type": "INFERRED", "linked_fact_ids": [], "evidence_links": [], "timing": {}, "location": ""}],
        unknown_events,
        injury_loc=injury,
    )

    # 4. Another participant involved
    _add(
        "Another participant may have been involved",
        "another participant caused the injury",
        persons + ["Unknown other participant"],
        base_events + [{"description": "A participant not identified in the available evidence may have been involved.", "event_type": "UNKNOWN", "linked_fact_ids": [], "evidence_links": [], "timing": {}, "location": ""}],
        unknown_events + ["Identity of any additional participant is unknown."],
        injury_loc=injury,
    )

    # 5. Pre-dating entry
    _add(
        "The fatal event may have occurred before entry",
        "the injury occurred before the recorded entry",
        persons,
        [{"description": "The fatal event occurred before the person was observed entering.", "event_type": "UNKNOWN", "linked_fact_ids": [], "evidence_links": [], "timing": {}, "location": ""}]
        + base_events,
        unknown_events + ["Pre-entry events are not established."],
        injury_loc=injury,
    )

    # 6. Post-dating exit
    _add(
        "The fatal event may have occurred after exit",
        "the injury occurred after the recorded exit",
        persons,
        base_events + [{"description": "The fatal event occurred after the person was observed leaving.", "event_type": "UNKNOWN", "linked_fact_ids": [], "evidence_links": [], "timing": {}, "location": ""}],
        unknown_events + ["Post-exit events are not established."],
        injury_loc=injury,
    )

    # 7. Evidence insufficient to distinguish
    _add(
        "Available evidence does not distinguish between causal sequences",
        "causal sequence not distinguishable",
        persons,
        base_events + [{"description": "Multiple causal sequences are compatible with the evidence; they cannot be distinguished.", "event_type": "UNKNOWN", "linked_fact_ids": [], "evidence_links": [], "timing": {}, "location": ""}],
        unknown_events,
        injury_loc=injury,
    )

    # 8. Object present but use not established
    if summary["has_knife"]:
        _add(
            "Knife present but its use is not established",
            "knife use not established",
            persons,
            base_events + [{"description": "A knife was present, but no evidence establishes that it caused the injury.", "event_type": "INFERRED", "linked_fact_ids": [], "evidence_links": [], "timing": {}, "location": ""}],
            unknown_events,
            injury_loc=injury,
        )

    # 9. Alternative sequence variations with explicit timing
    if summary["has_entry"] and summary["has_exit"]:
        _add(
            "Interaction during the unobserved window with entry and exit only",
            "unobserved window interaction",
            persons,
            base_events + [{"description": "Entry and exit are observed; the interaction in the unobserved window is not established.", "event_type": "UNKNOWN", "linked_fact_ids": [], "evidence_links": [], "timing": {}, "location": ""}],
            unknown_events,
            injury_loc=injury,
        )

    # 10. Similar-case-inspired alternative (analogical reference only)
    if similar_cases:
        patterns = [p for sc in similar_cases[:2] for p in sc.get("relevant_patterns", [])][:3]
        _add(
            "Alternative explanation analogous to documented reference cases",
            "alternative causal explanation",
            persons,
            base_events + [{"description": "A causal explanation analogous to documented reference cases is possible, but is not transferred as fact.", "event_type": "HYPOTHESIZED", "linked_fact_ids": [], "evidence_links": [], "timing": {}, "location": ""}],
            unknown_events,
            origin="SIMILAR_CASE_INSPIRED",
            patterns=patterns,
            injury_loc=injury,
        )

    # 11. IMPOSSIBLE: alternate injury location violating the forensic anchor.
    if injury and anchor_value:
        alternate = "chest" if injury != "chest" else "abdomen"
        _add(
            f"Injury located at the {alternate}",
            f"the injury was located at the {alternate}",
            persons,
            base_events + [{"description": f"The injury was located at the {alternate}.", "event_type": "INFERRED", "linked_fact_ids": [], "evidence_links": [], "timing": {}, "location": ""}],
            unknown_events,
            injury_loc=alternate,
        )

    # Trim to safety limit.
    candidates = candidates[: settings.MAX_HYPOTHESES]
    return {"hypotheses": candidates, "provider": "mock"}


def mock_critique(payload: dict[str, Any]) -> dict[str, Any]:
    scenario = payload.get("scenario", {})
    anchors = payload.get("anchors", [])
    issues: list[dict[str, Any]] = []
    scenario_injury = scenario.get("injury_location")

    for a in anchors:
        if a.get("type") == "INJURY_LOCATION":
            anchor_loc = a.get("value", {}).get("location")
            if scenario_injury and scenario_injury != anchor_loc:
                issues.append(
                    {
                        "type": "FORENSIC",
                        "description": f"Scenario asserts injury at {scenario_injury}; authoritative finding is {anchor_loc}.",
                        "severity": "HARD",
                        "fixable": False,
                        "constraint": f"ForensicAnchor {a.get('anchor_id')}",
                    }
                )

    # Unsupported claims: KNOWN events without linked facts.
    for ev in scenario.get("events", []):
        if ev.get("event_type") == "KNOWN" and not ev.get("linked_fact_ids"):
            issues.append(
                {
                    "type": "EVIDENTIARY",
                    "description": f"Scenario event is asserted as known without supporting facts: {ev.get('description', '')[:120]}",
                    "severity": "SOFT",
                    "fixable": True,
                    "constraint": "evidence support",
                }
            )

    hard = [i for i in issues if i["severity"] == "HARD"]
    verdict = "FAIL" if hard else "PASS"
    return {
        "verdict": verdict,
        "issues": issues,
        "summary": "Adversarial review completed.",
        "provider": "mock",
    }


def mock_revise(payload: dict[str, Any]) -> dict[str, Any]:
    scenario = payload.get("scenario", {})
    issues = payload.get("issues", [])
    hard = [i for i in issues if i["severity"] == "HARD"]
    if hard:
        return {"reject": True, "reason": hard[0].get("description", "hard conflict"), "provider": "mock"}
    revised = dict(scenario)
    events = list(revised.get("events", []))
    for i in issues:
        if i.get("fixable"):
            # Downgrade unsupported known claims to INFERRED.
            for ev in events:
                if ev.get("description") in i.get("description", "") or ev.get("event_type") == "KNOWN":
                    if not ev.get("linked_fact_ids"):
                        ev["event_type"] = "INFERRED"
    revised["events"] = events
    return {"reject": False, "revised": revised, "provider": "mock"}


def mock_expand_alternatives(payload: dict[str, Any]) -> dict[str, Any]:
    rejected = payload.get("rejected_scenario", {})
    facts = payload.get("facts", [])
    summary = _facts_summary(facts)
    injury = summary["injury"]
    new: list[dict[str, Any]] = []
    base_events = _make_scenario_events(summary, payload.get("timeline", []), "expand")
    if summary["has_entry"]:
        new.append(
            {
                "title": "Reordered sequence: event before observed entry",
                "summary": "The injury may have occurred before the person was observed entering the covered area.",
                "cause_claim": "event occurred before observed entry",
                "participants": summary["persons"],
                "events": base_events,
                "unknowns": ["Pre-entry sequence not established."],
                "origin": "EXPANSION",
                "similar_case_patterns_used": [],
                "injury_location": injury,
            }
        )
    if summary["has_exit"]:
        new.append(
            {
                "title": "Reordered sequence: event after observed exit",
                "summary": "The injury may have occurred after the person was observed exiting.",
                "cause_claim": "event occurred after observed exit",
                "participants": summary["persons"],
                "events": base_events,
                "unknowns": ["Post-exit sequence not established."],
                "origin": "EXPANSION",
                "similar_case_patterns_used": [],
                "injury_location": injury,
            }
        )
    return {"hypotheses": new[:4], "provider": "mock"}


def mock_summarize(payload: dict[str, Any]) -> dict[str, Any]:
    scenario = payload.get("scenario", {})
    parts = [
        scenario.get("summary", scenario.get("title", "")),
        f"Participants: {', '.join(scenario.get('participants', []) or ['not established'])}.",
        f"Causal claim: {scenario.get('cause_claim', 'not established')}.",
    ]
    unknowns = scenario.get("unknowns", [])
    if unknowns:
        parts.append(f"Unknown: {'; '.join(unknowns[:3])}.")
    return {"summary": " ".join(parts), "provider": "mock"}


def mock_similar_case_relevance(payload: dict[str, Any]) -> dict[str, Any]:
    similar = payload.get("similar_cases", [])
    patterns: list[str] = []
    for sc in similar[:3]:
        patterns.extend(sc.get("relevant_patterns", []))
    return {
        "patterns": list(dict.fromkeys(patterns))[:6],
        "note": "Retrieved cases are analogical references only; conclusions are not transferred.",
        "provider": "mock",
    }


def mock_compare(payload: dict[str, Any]) -> dict[str, Any]:
    scenarios = payload.get("scenarios", [])
    if len(scenarios) < 2:
        return {"shared": [], "differences": [], "discriminating": [], "note": "Need at least two scenarios.", "provider": "mock"}

    shared: list[str] = []
    diffs: list[str] = []
    disc: list[dict[str, Any]] = []

    def label(sc: dict[str, Any]) -> str:
        return sc.get("hypothesis_label") or sc.get("id", "?")

    # Participants in common / differing
    part_sets = [set(sc.get("participants", [])) for sc in scenarios]
    common_parts = set.intersection(*part_sets)
    if common_parts:
        shared.append(f"Participants in common: {', '.join(sorted(common_parts))}")
    for p in sorted(set.union(*part_sets) - common_parts):
        owners = [label(sc) for sc in scenarios if p in sc.get("participants", [])]
        diffs.append(f"Participant {p} appears only in {' and '.join(owners)}")

    # Evidence support: shared vs scenario-specific
    sup_sets = [set(sc.get("supporting_evidence", [])) for sc in scenarios]
    common_sup = set.intersection(*sup_sets)
    if common_sup:
        shared.append(f"Supported by {len(common_sup)} shared evidence item(s): {', '.join(sorted(common_sup))}")
    for sc in scenarios:
        only_here = set(sc.get("supporting_evidence", []))
        for other in scenarios:
            if other is not sc:
                only_here -= set(other.get("supporting_evidence", []))
        for eid in sorted(only_here):
            diffs.append(f"{label(sc)} is uniquely supported by {eid}")

    # Contradicting evidence in common
    con_sets = [set(sc.get("contradicting_evidence", [])) for sc in scenarios]
    common_con = set.intersection(*con_sets)
    if common_con:
        shared.append(f"Contradicted by shared evidence: {', '.join(sorted(common_con))}")

    # Differing causal claims
    claims = {label(sc): (sc.get("cause_claim") or "").strip() for sc in scenarios}
    uniq = {c for c in claims.values() if c}
    if len(uniq) > 1:
        diffs.append("Causal claims differ: " + "; ".join(f"{k}: {v}" for k, v in claims.items()))

    # Discriminating evidence: supports one scenario but not the other
    for i in range(len(scenarios)):
        for j in range(i + 1, len(scenarios)):
            a, b = scenarios[i], scenarios[j]
            only_a = set(a.get("supporting_evidence", [])) - set(b.get("supporting_evidence", []))
            only_b = set(b.get("supporting_evidence", [])) - set(a.get("supporting_evidence", []))
            parts = []
            if only_a:
                parts.append(f"{label(a)} uniquely supported by {', '.join(sorted(only_a))}")
            if only_b:
                parts.append(f"{label(b)} uniquely supported by {', '.join(sorted(only_b))}")
            if parts:
                disc.append({"pair": [label(a), label(b)], "note": " | ".join(parts)})
            elif a.get("unknown_count", 0) != b.get("unknown_count", 0):
                disc.append({
                    "pair": [label(a), label(b)],
                    "note": (
                        f"{label(a)} has {a.get('unknown_count', 0)} unknown event(s); "
                        f"{label(b)} has {b.get('unknown_count', 0)}. Resolving those periods would discriminate."
                    ),
                })

    if not disc:
        disc.append({
            "pair": [label(scenarios[0]), label(scenarios[1])],
            "note": "No single evidence item currently discriminates; both scenarios rest on the same support.",
        })

    return {
        "shared": shared,
        "differences": diffs,
        "discriminating": disc,
        "note": "Comparison is descriptive; no probability claim is made.",
        "provider": "mock",
    }