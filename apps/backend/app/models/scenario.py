from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, JsonType, TimestampMixin, gen_uuid


class Hypothesis(Base, TimestampMixin):
    __tablename__ = "hypotheses"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=gen_uuid)
    case_id: Mapped[str] = mapped_column(String(64), ForeignKey("cases.id"), index=True)
    hypothesis_id: Mapped[str] = mapped_column(String(32))  # H-001
    title: Mapped[str] = mapped_column(String(400), default="")
    description: Mapped[str] = mapped_column(String(6000), default="")
    generation_round: Mapped[int] = mapped_column(Integer, default=1)
    origin: Mapped[str] = mapped_column(String(40), default="INITIAL")  # INITIAL/REVISION/EXPANSION/SIMILAR_CASE_INSPIRED
    parent_hypothesis_id: Mapped[str] = mapped_column(String(64), default="")
    similar_case_ids: Mapped[list] = mapped_column(JsonType, default=list)
    similar_case_patterns_used: Mapped[list] = mapped_column(JsonType, default=list)
    extra: Mapped[dict] = mapped_column(JsonType, default=dict)


class Scenario(Base, TimestampMixin):
    __tablename__ = "scenarios"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=gen_uuid)
    case_id: Mapped[str] = mapped_column(String(64), ForeignKey("cases.id"), index=True)
    hypothesis_id: Mapped[str] = mapped_column(String(64), ForeignKey("hypotheses.id"))
    # PENDING/VALIDATING/SURVIVING/REJECTED
    status: Mapped[str] = mapped_column(String(24), default="PENDING", index=True)
    summary: Mapped[str] = mapped_column(String(6000), default="")
    cause_claim: Mapped[str] = mapped_column(String(1000), default="")
    participants: Mapped[list] = mapped_column(JsonType, default=list)
    rejection_reason: Mapped[str] = mapped_column(String(4000), default="")
    final_verdict: Mapped[str] = mapped_column(String(2000), default="")
    iteration_count: Mapped[int] = mapped_column(Integer, default=1)
    is_survivor: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    extra: Mapped[dict] = mapped_column(JsonType, default=dict)


class ScenarioEvent(Base, TimestampMixin):
    __tablename__ = "scenario_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=gen_uuid)
    scenario_id: Mapped[str] = mapped_column(String(64), ForeignKey("scenarios.id"), index=True)
    case_id: Mapped[str] = mapped_column(String(64), ForeignKey("cases.id"), index=True)
    event_order: Mapped[int] = mapped_column(Integer, default=0)
    description: Mapped[str] = mapped_column(String(2000), default="")
    # KNOWN | INFERRED | UNKNOWN | HYPOTHESIZED
    event_type: Mapped[str] = mapped_column(String(24), default="HYPOTHESIZED")
    linked_fact_ids: Mapped[list] = mapped_column(JsonType, default=list)
    evidence_links: Mapped[list] = mapped_column(JsonType, default=list)
    timing: Mapped[dict] = mapped_column(JsonType, default=dict)
    location: Mapped[str] = mapped_column(String(300), default="")


class ScenarioEvidenceLink(Base, TimestampMixin):
    __tablename__ = "scenario_evidence_links"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=gen_uuid)
    scenario_id: Mapped[str] = mapped_column(String(64), ForeignKey("scenarios.id"), index=True)
    case_id: Mapped[str] = mapped_column(String(64), ForeignKey("cases.id"), index=True)
    evidence_item_id: Mapped[str] = mapped_column(String(64), ForeignKey("evidence_items.id"), index=True)
    link_type: Mapped[str] = mapped_column(String(16), default="SUPPORTING")  # SUPPORTING/CONTRADICTING/NEUTRAL
    rationale: Mapped[str] = mapped_column(String(1000), default="")
    fact_ids: Mapped[list] = mapped_column(JsonType, default=list)


class ScenarioScore(Base, TimestampMixin):
    __tablename__ = "scenario_scores"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=gen_uuid)
    scenario_id: Mapped[str] = mapped_column(String(64), ForeignKey("scenarios.id"), index=True)
    total: Mapped[int] = mapped_column(Integer, default=0)
    breakdown: Mapped[dict] = mapped_column(JsonType, default=dict)
    version: Mapped[str] = mapped_column(String(40), default="1.0")


class DiscriminatingEvidence(Base, TimestampMixin):
    __tablename__ = "discriminating_evidence"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=gen_uuid)
    case_id: Mapped[str] = mapped_column(String(64), ForeignKey("cases.id"), index=True)
    scenario_pair: Mapped[list] = mapped_column(JsonType, default=list)  # ["H-001","H-007"]
    shared_evidence: Mapped[list] = mapped_column(JsonType, default=list)
    differing_evidence: Mapped[list] = mapped_column(JsonType, default=list)
    needed_evidence: Mapped[list] = mapped_column(JsonType, default=list)
    note: Mapped[str] = mapped_column(String(2000), default="")


class ScenarioComparison(Base, TimestampMixin):
    __tablename__ = "scenario_comparisons"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=gen_uuid)
    case_id: Mapped[str] = mapped_column(String(64), ForeignKey("cases.id"), index=True)
    scenario_ids: Mapped[list] = mapped_column(JsonType, default=list)
    result: Mapped[dict] = mapped_column(JsonType, default=dict)