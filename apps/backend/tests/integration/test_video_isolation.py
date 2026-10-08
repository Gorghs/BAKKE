from __future__ import annotations

from app.features.visualization.director import VideoDirectorAgent, build_visual_spec
from app.models import ForensicAnchor, Hypothesis, Scenario, ScenarioEvent
from tests.conftest import make_case

FORBIDDEN = [
    "E-001",
    "E-002",
    "E-003",
    "e-00",
    "witness",
    "similar case",
    "reference case",
    "hypothesis score",
    "evidence consistency",
    "right hip",
    "rejection",
    "cause claim",
    "recommendation",
    "most likely",
    "score 95",
    "95.",
]


class TestVideoPromptIsolation:
    def test_final_video_prompt_is_visual_only(self, db, dev_user):
        case = make_case(db, dev_user)
        hyp = Hypothesis(
            case_id=case.id,
            hypothesis_id="H-001",
            title="A",
            description="leak test",
            origin="INITIAL",
            extra={},
        )
        db.add(hyp)
        db.flush()
        sc = Scenario(
            case_id=case.id,
            hypothesis_id=hyp.id,
            status="SURVIVING",
            is_survivor=True,
            # Deliberately poisoned with reasoning text that must never reach the video provider.
            summary="E-001 shows the suspect inflicted the right hip injury; witness E-002 contradicts; score 95.",
            cause_claim="E-001: suspect caused injury",
            participants=["Person A", "Person B"],
            extra={"injury_location": "right hip"},
        )
        db.add(sc)
        db.flush()
        db.add(
            ScenarioEvent(
                scenario_id=sc.id,
                case_id=case.id,
                event_order=0,
                description="Person A entered the hallway.",
                event_type="KNOWN",
                linked_fact_ids=[],
                evidence_links=[],
                timing={"start": "20:05"},
                location="Hallway",
            )
        )
        db.add(ForensicAnchor(case_id=case.id, anchor_id="FA-001", type="INJURY_LOCATION", value={"location": "right hip"}, normalized="right hip", source_evidence_ids=["E-001"]))
        db.commit()

        events = db.query(ScenarioEvent).filter_by(scenario_id=sc.id).order_by(ScenarioEvent.event_order).all()
        anchors = [{"type": a.type, "value": a.value} for a in db.query(ForensicAnchor).filter_by(case_id=case.id).all()]

        spec = build_visual_spec(sc, events, anchors)
        assert spec.get("visual_only") is True
        director = VideoDirectorAgent()
        directed = director.direct(spec, events)
        prompt = directed["visual_prompt"]

        low = prompt.lower()
        for token in FORBIDDEN:
            assert token not in low, f"video prompt leaked '{token}'"

        # Internal identifiers must never reach the visual prompt.
        assert str(hyp.id) not in prompt, "hypothesis UUID leaked into video prompt"
        assert str(sc.id) not in prompt, "scenario UUID leaked into video prompt"

        # The visual-only label must be present in the final prompt.
        assert "NOT RECORDED FOOTAGE" in prompt
        assert "3D ANIMATED SCENARIO VISUALIZATION" in prompt
        assert "ANIMATION" in prompt and "SHOT LIST" in prompt

    def test_visual_spec_excludes_reasoning_keys(self, db, dev_user):
        case = make_case(db, dev_user)
        hyp = Hypothesis(case_id=case.id, hypothesis_id="H-001", title="A", origin="INITIAL", extra={})
        db.add(hyp)
        db.flush()
        sc = Scenario(
            case_id=case.id,
            hypothesis_id=hyp.id,
            status="SURVIVING",
            is_survivor=True,
            summary="x",
            cause_claim="y",
            participants=["Person A"],
            extra={"injury_location": "right hip"},
        )
        db.add(sc)
        db.commit()
        spec = build_visual_spec(sc, [], [])
        # The visual spec object itself must not carry case/evidence/reasoning payloads.
        assert "facts" not in spec
        assert "evidence" not in spec
        assert "reports" not in spec
        assert "findings" not in spec
        assert set(spec.keys()) <= {
            "label",
            "title",
            "environment",
            "locations",
            "characters",
            "objects",
            "unknown_periods",
            "aspect_ratio",
            "constraints",
            "visual_only",
            "shots",
            "total_duration",
            "visual_prompt",
        }
