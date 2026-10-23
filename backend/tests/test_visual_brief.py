from __future__ import annotations

from app.agents.director import VideoDirectorAgent, build_visual_spec
from app.agents.visual_brief import (
    brief_problem,
    derive_visual_brief,
    request_visual_brief,
    source_text,
)
from app.models import Hypothesis, Scenario, ScenarioEvent
from app.services.video_service import VideoService, _scene_for_mock
from tests.conftest import make_case

SUMMARY = "An unknown person entered the yard after 19:12 and removed the padlock."
TITLE = "Padlock Removed by External Visitor"


def _events() -> list[dict]:
    return [
        {
            "description": "No vehicle entered between 19:12 and 07:50",
            "event_type": "UNKNOWN",
            "timing": {"time": "19:12-07:50"},
            "location": "yard",
        },
        {
            "description": "Padlock missing at 07:50",
            "event_type": "KNOWN",
            "timing": {"time": "07:50"},
            "location": "store door",
        },
    ]


def _payload(summary: str = SUMMARY) -> dict:
    return {
        "hypothesis_title": TITLE,
        "scenario_summary": summary,
        "participants": [],
        "events": _events(),
        "unknowns": [],
    }


def _brief() -> dict:
    return derive_visual_brief(
        summary=SUMMARY,
        title=TITLE,
        participants=[],
        events=_events(),
        locations=["Yard", "Store Door"],
    )


def _h004(db, dev_user):
    case = make_case(db, dev_user)
    hyp = Hypothesis(
        case_id=case.id,
        hypothesis_id="H-004",
        title=TITLE,
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
        summary=SUMMARY,
        cause_claim="",
        participants=[],
        extra={},
    )
    db.add(sc)
    db.flush()
    for order, event in enumerate(_events()):
        db.add(
            ScenarioEvent(
                scenario_id=sc.id,
                case_id=case.id,
                event_order=order,
                description=event["description"],
                event_type=event["event_type"],
                linked_fact_ids=[],
                evidence_links=[],
                timing=event["timing"],
                location=event["location"],
            )
        )
    db.commit()
    return case, hyp, sc


def _directed_of(db, dev_user, summary: str, events: list[dict], locations: list[str] | None = None):
    """Persist a scenario of arbitrary content and run the director over it."""
    case = make_case(db, dev_user)
    hyp = Hypothesis(
        case_id=case.id, hypothesis_id="H-004", title="Test", origin="INITIAL", extra={}
    )
    db.add(hyp)
    db.flush()
    sc = Scenario(
        case_id=case.id,
        hypothesis_id=hyp.id,
        status="SURVIVING",
        is_survivor=True,
        summary=summary,
        cause_claim="",
        participants=[],
        extra={},
    )
    db.add(sc)
    db.flush()
    for order, event in enumerate(events):
        db.add(
            ScenarioEvent(
                scenario_id=sc.id,
                case_id=case.id,
                event_order=order,
                description=event["description"],
                event_type=event.get("event_type", "KNOWN"),
                linked_fact_ids=[],
                evidence_links=[],
                timing=event.get("timing", {}),
                location=event.get("location", ""),
            )
        )
    db.commit()
    rows = db.query(ScenarioEvent).filter_by(scenario_id=sc.id).order_by("event_order").all()
    sc.hypothesis_label = hyp.hypothesis_id
    spec = build_visual_spec(sc, rows, [], title=hyp.title)
    return VideoDirectorAgent().direct(spec, rows)


class _FakeLLM:
    name = "fake-llm"
    is_mock = False
    label = "FAKE"

    def __init__(self, reply: dict | None = None, exc: Exception | None = None) -> None:
        self.reply = reply or {}
        self.exc = exc
        self.calls: list[tuple[str, dict]] = []

    def run_task(self, task: str, payload: dict) -> dict:
        self.calls.append((task, payload))
        if self.exc:
            raise self.exc
        return self.reply


class TestDeriveVisualBrief:
    def test_named_actor_prop_and_removal(self):
        brief = _brief()
        assert [actor["label"] for actor in brief["actors"]] == ["Unknown person"]
        assert len(brief["props"]) == 1
        prop = brief["props"][0]
        assert (prop["label"], prop["start_state"], prop["end_state"]) == (
            "padlock",
            "present",
            "missing",
        )
        assert prop["location"] == "store door"
        assert [beat["action"] for beat in brief["beats"]] == [
            "entered the yard after 19:12",
            "removed the padlock",
        ]

    def test_absence_is_recorded_but_is_not_an_action(self):
        brief = _brief()
        assert brief["absences"] == ["vehicle"]
        assert all("vehicle" not in beat["action"] for beat in brief["beats"])

    def test_poisoned_summary_adds_no_beats_and_no_props(self):
        brief = derive_visual_brief(
            summary="E-001 shows the suspect inflicted the right hip injury; witness E-002 "
            "contradicts; score 95.",
            title="A",
            participants=["Person A"],
            events=[],
            locations=["Hallway"],
        )
        assert [actor["label"] for actor in brief["actors"]] == ["Person A"]
        assert brief["beats"] == []
        assert brief["props"] == []

    def test_derived_brief_passes_the_gate(self):
        assert brief_problem(_brief(), source_text(_payload())) == ""


class TestBriefGate:
    def _with(self, brief: dict, **patch) -> dict:
        out = {**brief, **patch}
        return out

    def test_actor_must_be_named_in_the_scenario(self):
        brief = self._with(
            _brief(), actors=[{"label": "Delivery driver", "appearance": "", "clothing": ""}]
        )
        assert "not named in the scenario" in brief_problem(brief, source_text(_payload()))

    def test_invented_prop_is_rejected(self):
        brief = self._with(
            _brief(),
            props=[
                {
                    "label": "window",
                    "start_state": "closed",
                    "end_state": "open",
                    "location": "store door",
                }
            ],
        )
        assert "prop 'window'" in brief_problem(brief, source_text(_payload()))

    def test_invented_action_is_rejected(self):
        brief = self._with(
            _brief(), beats=[{"clock": "", "actor": "Unknown person", "action": "opens the window"}]
        )
        assert "not stated in the scenario" in brief_problem(brief, source_text(_payload()))

    def test_reasoning_text_is_rejected(self):
        brief = self._with(_brief(), continuity=["A witness places the suspect at the door."])
        assert "forbidden token" in brief_problem(brief, source_text(_payload()))

    def test_evidence_id_is_rejected(self):
        brief = self._with(_brief(), continuity=["E-001 was recovered beside the door."])
        assert brief_problem(brief, source_text(_payload())) != ""

    def test_absence_noun_must_be_named(self):
        brief = self._with(_brief(), absences=["helicopter"])
        assert "absence 'helicopter'" in brief_problem(brief, source_text(_payload()))

    def test_oversized_brief_is_rejected(self):
        brief = self._with(_brief(), continuity=["the space holds"] * 7)
        assert brief_problem(brief, source_text(_payload())) != ""

    def test_sharing_one_word_is_not_containment(self):
        # "store window" shares "store" with the scenario; an overlap test passed
        # it, a containment test does not.
        brief = self._with(
            _brief(),
            props=[
                {
                    "label": "store window",
                    "start_state": "closed",
                    "end_state": "open",
                    "location": "",
                }
            ],
        )
        assert "prop 'store window'" in brief_problem(brief, source_text(_payload()))

    def test_invented_clock_is_rejected(self):
        brief = self._with(
            _brief(),
            beats=[{"clock": "03:00", "actor": "Unknown person", "action": "entered the yard"}],
        )
        assert "clock '03:00'" in brief_problem(brief, source_text(_payload()))

    def test_invented_setting_is_rejected(self):
        brief = self._with(_brief(), setting="the yard behind the shed")
        assert "not named in the scenario" in brief_problem(brief, source_text(_payload()))


class TestBriefDerivationEdges:
    def test_opened_object_keeps_its_own_state(self):
        brief = derive_visual_brief(
            summary="An unknown person opened the till.",
            title="",
            participants=[],
            events=[],
            locations=["Shop Floor"],
        )
        prop = brief["props"][0]
        assert prop["label"] == "till"
        assert prop["end_state"] == "open"

    def test_comma_separated_summary_gives_one_beat_each(self):
        brief = derive_visual_brief(
            summary="An unknown person entered the yard, crossed to the door, removed the padlock.",
            title="",
            participants=[],
            events=[],
            locations=["Yard", "Store Door"],
        )
        assert [beat["action"] for beat in brief["beats"]] == [
            "entered the yard",
            "crossed to the door",
            "removed the padlock",
        ]

    def test_unqualified_actor_still_gives_an_action_shot(self):
        brief = derive_visual_brief(
            summary="A person removed the padlock from the store door.",
            title="",
            participants=[],
            events=[],
            locations=["Store Door"],
        )
        assert [actor["label"] for actor in brief["actors"]] == ["Person"]
        assert [beat["action"] for beat in brief["beats"]] == ["removed the padlock from the store door"]

    def test_action_without_an_actor_is_reported_not_animated(self):
        brief = derive_visual_brief(
            summary="The padlock was removed from the store door.",
            title="",
            participants=[],
            events=[],
            locations=["Store Door"],
        )
        assert brief["beats"] == []
        assert any("removed from the store door" in line for line in brief["unshown"])


class TestPromptContent:
    def _directed(self, db, dev_user):
        case, hyp, sc = _h004(db, dev_user)
        events = db.query(ScenarioEvent).filter_by(scenario_id=sc.id).order_by("event_order").all()
        sc.hypothesis_label = hyp.hypothesis_id
        spec = build_visual_spec(sc, events, [], title=hyp.title)
        return VideoDirectorAgent().direct(spec, events)

    def test_one_padlock_and_an_explicit_end_state(self, db, dev_user):
        prompt = self._directed(db, dev_user)["visual_prompt"]
        assert "exactly one padlock" in prompt.lower()
        assert "no padlock appears after that" in prompt.lower()
        assert "no padlock is on the store door" in prompt.lower()

    def test_actor_is_an_abstract_dummy(self, db, dev_user):
        prompt = self._directed(db, dev_user)["visual_prompt"]
        assert "stylised dummy figure" in prompt
        assert "featureless face" in prompt
        assert "no facial detail at any point" in prompt

    def test_absence_never_becomes_a_shot(self, db, dev_user):
        directed = self._directed(db, dev_user)
        for shot in directed["shots"]:
            blob = " ".join(
                [
                    shot.get("description", ""),
                    shot.get("framing", ""),
                    shot.get("direction", ""),
                    shot.get("camera", ""),
                    " ".join(a.get("description", "") for a in shot.get("action", [])),
                ]
            ).lower()
            assert "vehicle" not in blob
        assert "Do not show any vehicle." in directed["visual_prompt"]

    def test_shots_cover_the_clip_in_order(self, db, dev_user):
        directed = self._directed(db, dev_user)
        assert directed["total_duration"] == 10.0
        assert directed["shots"][0]["start_seconds"] == 0.0
        for previous, following in zip(directed["shots"], directed["shots"][1:]):
            assert previous["end_seconds"] == following["start_seconds"]
        assert directed["shots"][-1]["end_seconds"] == 10.0
        # The scenario states two actions and one end state, so four shots.
        assert [s["kind"] for s in directed["shots"]] == [
            "establishing",
            "action",
            "action",
            "state",
        ]


class TestShotTiming:
    def test_clocks_follow_the_scenario_not_the_row_order(self, db, dev_user):
        # The same two events, stored the other way round: 07:50 first, then the
        # 19:12-07:50 window. Row order would put the morning before the evening.
        events = [
            {
                "description": "Padlock missing at 07:50",
                "timing": {"time": "07:50"},
                "location": "store door",
            },
            {
                "description": "No vehicle entered between 19:12 and 07:50",
                "timing": {"time": "19:12-07:50"},
                "location": "yard",
            },
        ]
        directed = _directed_of(
            db, dev_user, "An unknown person entered the yard after 19:12 and removed the padlock.", events
        )
        assert "evening (19:12) through early morning (07:50)" in directed["visual_prompt"]
        assert directed["shots"][0]["clock"] == "19:12"
        assert directed["shots"][-1]["clock"] == "07:50"

    def test_beat_clock_is_its_own_not_the_whole_window(self, db, dev_user):
        directed = _directed_of(
            db,
            dev_user,
            "An unknown person entered the yard after 19:12 and removed the padlock.",
            [
                {
                    "description": "No vehicle entered between 19:12 and 07:50",
                    "event_type": "UNKNOWN",
                    "timing": {"time": "19:12-07:50"},
                    "location": "yard",
                },
                {
                    "description": "Padlock missing at 07:50",
                    "timing": {"time": "07:50"},
                    "location": "store door",
                },
            ],
        )
        # The removal follows the entry, so it inherits 19:12. Printing the window
        # stamped a two-second action with eleven hours.
        assert directed["shots"][2]["clock"] == "19:12"
        assert "clock 19:12 to 07:50" not in directed["visual_prompt"]

    def test_place_name_never_doubles_its_article(self, db, dev_user):
        directed = _directed_of(
            db,
            dev_user,
            "An unknown person entered the yard and crossed to the door.",
            [{"description": "Nothing recorded in the yard", "timing": {"time": "18:00"}, "location": "yard"}],
        )
        assert "the the" not in directed["visual_prompt"].lower()
        assert "Close on the yard" in directed["visual_prompt"]

    def test_shot_count_stays_inside_the_limit(self, db, dev_user):
        directed = _directed_of(
            db,
            dev_user,
            "An unknown person entered the yard, crossed to the door, opened the padlock, "
            "took the tools, left the yard.",
            [
                {"description": "Tools missing at 07:50", "timing": {"time": "07:50"}, "location": "yard"},
            ],
        )
        assert len(directed["shots"]) <= VideoDirectorAgent.MAX_SHOTS
        # Folding keeps every action; it drops none of them.
        action_text = " ".join(
            a["description"] for shot in directed["shots"] for a in shot.get("action", [])
        )
        assert "opens the padlock" in action_text
        assert "takes the tools" in action_text


class TestTimecode:
    def test_each_shot_carries_its_own_clock_on_screen(self, db, dev_user):
        directed = _directed_of(
            db,
            dev_user,
            "An unknown person entered the yard after 19:12 and removed the padlock.",
            [
                {
                    "description": "No vehicle entered between 19:12 and 07:50",
                    "event_type": "UNKNOWN",
                    "timing": {"time": "19:12-07:50"},
                    "location": "yard",
                },
                {
                    "description": "Padlock missing at 07:50",
                    "timing": {"time": "07:50"},
                    "location": "store door",
                },
            ],
        )
        prompt = directed["visual_prompt"]
        assert "On-screen timecode: 19:12" in prompt
        assert "On-screen timecode: 07:50" in prompt
        # The clock is a reading of the shot, never a counter running with the clip.
        assert "holds that reading for the whole shot" in prompt
        assert "top right corner" in prompt
        # Nothing else on screen may carry text or digits.
        assert "Render no other words, digits, signage or captions" in prompt

    def test_clip_without_a_clock_asks_for_no_timecode(self, db, dev_user):
        directed = _directed_of(
            db,
            dev_user,
            "An unknown person entered the yard and removed the padlock.",
            [{"description": "Padlock missing in the store door", "location": "store door"}],
        )
        # No stated time means no time on screen: the clip cannot invent one.
        assert "On-screen timecode" not in directed["visual_prompt"]
        assert all(not shot["clock"] for shot in directed["shots"])

    def test_mock_scene_places_the_clock_on_the_clip_timeline(self):
        directed = {
            "label": "HYPOTHESIS H-004",
            "total_duration": 10.0,
            "characters": [],
            "objects": [],
            "shots": [
                {"index": 1, "start_seconds": 0.0, "end_seconds": 2.0, "clock": "19:12"},
                {"index": 2, "start_seconds": 2.0, "end_seconds": 10.0, "clock": "07:50"},
            ],
        }
        scene = _scene_for_mock(directed)
        assert scene["timecodes"] == [
            {"start": 0.0, "end": 0.2, "clock": "19:12"},
            {"start": 0.2, "end": 1.0, "clock": "07:50"},
        ]


class TestBriefSelection:
    def test_invented_brief_falls_back_to_the_scenario(self, db, dev_user, monkeypatch):
        import app.providers.registry as registry

        bad = {
            "setting": "a yard",
            "actors": [],
            "props": [
                {"label": "window", "start_state": "closed", "end_state": "open", "location": ""}
            ],
            "beats": [],
            "continuity": [],
            "absences": [],
        }
        monkeypatch.setattr(registry, "get_llm_provider", lambda: _FakeLLM(bad))
        case, hyp, sc = _h004(db, dev_user)
        spec = VideoService().build_spec(db, sc, force=True).spec
        assert spec["visual_brief"]["used"] is False
        assert "prop 'window'" in spec["visual_brief"]["reason"]
        assert all(prop["label"] != "window" for prop in spec["props"])
        assert "padlock" in spec["visual_prompt"].lower()

    def test_accepted_brief_is_used(self, db, dev_user, monkeypatch):
        import app.providers.registry as registry

        good = _brief()
        llm = _FakeLLM(good)
        monkeypatch.setattr(registry, "get_llm_provider", lambda: llm)
        case, hyp, sc = _h004(db, dev_user)
        spec = VideoService().build_spec(db, sc, force=True).spec
        assert spec["visual_brief"]["used"] is True
        assert llm.calls[0][0] == "build_visual_brief"
        # The payload carries the scenario's own visual content, not the case.
        payload = llm.calls[0][1]
        assert set(payload) == {
            "hypothesis_title",
            "scenario_summary",
            "participants",
            "events",
            "unknowns",
        }

    def test_incomplete_brief_keeps_the_stated_action(self, monkeypatch):
        import app.providers.registry as registry

        partial = {
            "setting": "",
            "actors": [],
            "props": [],
            "beats": [{"clock": "19:12", "actor": "Unknown person", "action": "entered the yard"}],
            "continuity": [],
            "absences": [],
        }
        monkeypatch.setattr(registry, "get_llm_provider", lambda: _FakeLLM(partial))
        brief, meta = request_visual_brief(_payload())
        assert meta["used"] is True
        # The model kept the entry and dropped the removal; the merge restores it.
        assert [beat["action"] for beat in brief["beats"]] == [
            "entered the yard",
            "removed the padlock",
        ]
        assert [actor["label"] for actor in brief["actors"]] == ["Unknown person"]
        assert [prop["label"] for prop in brief["props"]] == ["padlock"]
        assert brief["absences"] == ["vehicle"]

    def test_provider_failure_falls_back(self, monkeypatch):
        import app.providers.registry as registry

        monkeypatch.setattr(
            registry, "get_llm_provider", lambda: _FakeLLM(exc=RuntimeError("upstream down"))
        )
        brief, meta = request_visual_brief(_payload())
        assert brief is None
        assert meta["used"] is False
        assert "upstream down" in meta["reason"]
