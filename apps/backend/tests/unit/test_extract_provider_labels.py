from __future__ import annotations

import app.features.evidence.extract as extract_mod
from app.features.evidence.extract import DocumentAgent, ImageAgent, VideoEvidenceAgent
from app.models import EvidenceItem


class _FakeProvider:
    def __init__(self, name: str, label: str, is_mock: bool) -> None:
        self.name = name
        self.label = label
        self.is_mock = is_mock


def _evidence(item_type: str) -> EvidenceItem:
    return EvidenceItem(case_id="case-1", evidence_id="E-001", item_type=item_type, title="t")


def test_image_agent_records_vision_provider_label(monkeypatch):
    monkeypatch.setattr(
        extract_mod,
        "get_vision_provider",
        lambda: _FakeProvider("fake-vision", "live:vision-model", False),
    )
    agent = ImageAgent()
    agent.extract(_evidence("IMAGE"), text="visible: a hallway")
    assert agent.provider_label == "live:vision-model"


def test_video_agent_records_video_understanding_provider_label(monkeypatch):
    monkeypatch.setattr(
        extract_mod,
        "get_video_understanding_provider",
        lambda: _FakeProvider("fake-video-understanding", "live:vu-model", False),
    )
    agent = VideoEvidenceAgent()
    agent.extract(_evidence("VIDEO"), text="visible: person walking")
    assert agent.provider_label == "live:vu-model"


def test_document_agent_records_text_llm_label():
    agent = DocumentAgent()
    agent.extract(_evidence("INVESTIGATOR_REPORT"), text="Person A entered at 20:05.")
    assert agent.provider_label == agent.llm.label


def test_image_agent_reports_mock_vision_label(monkeypatch):
    monkeypatch.setattr(
        extract_mod,
        "get_vision_provider",
        lambda: _FakeProvider("mock-vision", "DEVELOPMENT MOCK", True),
    )
    agent = ImageAgent()
    agent.extract(_evidence("IMAGE"), text="visible: a hallway")
    assert agent.provider_label == "DEVELOPMENT MOCK"
