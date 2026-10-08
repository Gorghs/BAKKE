from __future__ import annotations

from typing import Any

from app.infrastructure.agents.base import BaseAgent, AgentError
from app.infrastructure.agents.contracts import ExtractionResult
from app.models import EvidenceItem
from app.config import get_settings
from app.infrastructure.providers.registry import get_stt_provider, get_vision_provider, get_video_understanding_provider

settings = get_settings()


def _extract_text_from_file(path: str, mime_type: str) -> str:
    import os

    if not path or not os.path.exists(path):
        return ""
    if mime_type in ("application/pdf",) or path.endswith(".pdf"):
        from pypdf import PdfReader

        reader = PdfReader(path)
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    if mime_type in (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ) or path.endswith(".docx"):
        import docx

        d = docx.Document(path)
        return "\n".join(p.text for p in d.paragraphs)
    with open(path, "r", errors="ignore") as f:
        return f.read()


class DocumentAgent(BaseAgent):
    """Extracts entities, facts, timestamps, locations from documents."""

    name = "DocumentAgent"

    def extract(self, evidence: EvidenceItem, text: str = "") -> ExtractionResult:
        payload = {
            "text": text,
            "evidence_type": evidence.item_type,
            "evidence_id": evidence.evidence_id,
            "source_type": evidence.item_type,
        }
        raw = self.run_task("extract_evidence", payload)
        return ExtractionResult.model_validate(raw)


class ForensicReportAgent(DocumentAgent):
    name = "ForensicReportAgent"

    def extract(self, evidence: EvidenceItem, text: str = "") -> ExtractionResult:
        result = super().extract(evidence, text)
        for f in result.facts:
            f.category = "FORENSIC"
            f.constraint_strength = "HARD"
            f.is_authoritative = True
        for fd in result.findings:
            fd.category = "FORENSIC"
            fd.status = "AUTHORITATIVE_SOURCE_FINDING"
            fd.strength = "HARD"
        return result


class PostMortemAgent(DocumentAgent):
    name = "PostMortemAgent"

    def extract(self, evidence: EvidenceItem, text: str = "") -> ExtractionResult:
        result = super().extract(evidence, text)
        for f in result.facts:
            f.category = "POST_MORTEM"
            f.constraint_strength = "HARD"
            f.is_authoritative = True
        for fd in result.findings:
            fd.category = "POST_MORTEM"
            fd.status = "AUTHORITATIVE_SOURCE_FINDING"
            fd.strength = "HARD"
        return result


class InvestigatorReportAgent(DocumentAgent):
    name = "InvestigatorReportAgent"

    def extract(self, evidence: EvidenceItem, text: str = "") -> ExtractionResult:
        result = super().extract(evidence, text)
        for fd in result.findings:
            fd.category = "INVESTIGATOR"
        return result


class WitnessStatementAgent(DocumentAgent):
    name = "WitnessStatementAgent"

    def extract(self, evidence: EvidenceItem, text: str = "") -> ExtractionResult:
        result = super().extract(evidence, text)
        for f in result.facts:
            if f.status == "HARD":
                f.status = "SOFT"
                f.constraint_strength = "SOFT"
        for fd in result.findings:
            fd.category = "WITNESS"
            fd.strength = "SOFT"
        return result


class AudioAgent(BaseAgent):
    """Transcribes audio and structures the transcript."""

    name = "AudioAgent"

    def extract(self, evidence: EvidenceItem, text: str = "") -> ExtractionResult:
        stt = get_stt_provider()
        transcript = text
        if not transcript and evidence.file_path:
            transcript = stt.transcribe(evidence.file_path)
        payload = {
            "text": transcript or "(no transcript available in mock mode)",
            "evidence_type": "AUDIO",
            "evidence_id": evidence.evidence_id,
            "source_type": "AUDIO",
        }
        raw = self.run_task("extract_evidence", payload)
        result = ExtractionResult.model_validate(raw)
        return result


class ImageAgent(BaseAgent):
    """Extracts visible objects, people, locations from images."""

    name = "ImageAgent"

    def extract(self, evidence: EvidenceItem, text: str = "") -> ExtractionResult:
        vision = get_vision_provider()
        prompt = (
            "Analyze this image as crime-scene evidence. Return JSON with 'objects', "
            "'people', 'locations' and 'notes'. Only report what is visible; never infer unseen events."
        )
        analysis = {}
        if evidence.file_path:
            analysis = vision.analyze_image(evidence.file_path, prompt)
        text = text or evidence.description or ""
        if analysis.get("objects"):
            text += " Visible objects: " + ", ".join(analysis["objects"])
        if analysis.get("people"):
            text += " Visible people: " + ", ".join(analysis["people"])
        payload = {
            "text": text or "(no visual analysis available in mock mode)",
            "evidence_type": "IMAGE",
            "evidence_id": evidence.evidence_id,
            "source_type": "IMAGE",
        }
        raw = self.run_task("extract_evidence", payload)
        result = ExtractionResult.model_validate(raw)
        return result


class VideoEvidenceAgent(BaseAgent):
    """Extracts visible people, objects, movement, timestamps from video."""

    name = "VideoEvidenceAgent"

    def extract(self, evidence: EvidenceItem, text: str = "") -> ExtractionResult:
        vu = get_video_understanding_provider()
        prompt = (
            "Analyze this video as evidence. Return JSON with 'people', 'objects', "
            "'timestamps' and 'notes'. Only report what is visible; never infer unseen events."
        )
        analysis = {}
        if evidence.file_path:
            analysis = vu.understand_video(evidence.file_path, prompt)
        text = text or evidence.description or ""
        for fa in analysis.get("frame_analyses", []):
            text += f" Frame {fa.get('frame')}: " + str(fa.get("analysis", ""))
        payload = {
            "text": text or "(no video analysis available in mock mode)",
            "evidence_type": "VIDEO",
            "evidence_id": evidence.evidence_id,
            "source_type": "VIDEO",
        }
        raw = self.run_task("extract_evidence", payload)
        result = ExtractionResult.model_validate(raw)
        return result


EXTRACTOR_AGENTS = {
    "FORENSIC_REPORT": ForensicReportAgent,
    "POST_MORTEM_REPORT": PostMortemAgent,
    "INVESTIGATOR_REPORT": InvestigatorReportAgent,
    "WITNESS_STATEMENT": WitnessStatementAgent,
    "TEXT": DocumentAgent,
    "DOCUMENT": DocumentAgent,
    "AUDIO": AudioAgent,
    "IMAGE": ImageAgent,
    "VIDEO": VideoEvidenceAgent,
    "PHYSICAL_EVIDENCE": DocumentAgent,
    "LOCATION_RECORD": DocumentAgent,
    "DIGITAL_RECORD": DocumentAgent,
    "OTHER": DocumentAgent,
}


def get_extractor_agent(item_type: str) -> BaseAgent:
    cls = EXTRACTOR_AGENTS.get(item_type, DocumentAgent)
    return cls()