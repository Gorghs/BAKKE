from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.domain.contracts import HypothesisDraft, ScenarioEventDraft
from app.features.analysis.reasoning_agent import (
    HypothesisCriticAgent,
    HypothesisRevisionAgent,
    InvestigativeReasoningAgent,
)
from app.config import get_settings
from app.domain.constraints.engine import ConstraintEngine, ConstraintViolation
from app.infrastructure.ids import Ids
from app.models import (
    AuditEvent,
    DiscriminatingEvidence,
    EvidenceItem,
    Fact,
    ForensicAnchor,
    Hypothesis,
    Scenario,
    ScenarioEvent,
    ScenarioEvidenceLink,
    ScenarioScore,
    SimilarCase,
    TimelineEvent,
)
from app.domain.dedup import deduplicate
from app.domain.ranking import rank_scenarios
from app.domain.scoring import compute_evidence_consistency_score

settings = get_settings()

STATE_PENDING = "PENDING"
STATE_VALIDATING = "VALIDATING"
STATE_SURVIVING = "SURVIVING"
STATE_REJECTED = "REJECTED"


class ReasoningResult:
    def __init__(self) -> None:
        self.total_generated = 0
        self.surviving = 0
        self.rejected = 0
        self.merged = 0
        self.iterations = 0
        self.stopped_reason = ""
        self.expansions = 0
        self.revisions = 0


def _fact_dict(f: Fact) -> dict[str, Any]:
    return {"fact_id": f.fact_id, "statement": f.statement, "status": f.status, "source_evidence_ids": f.source_evidence_ids, "metadata": f.extra}


def _anchor_dict(a: ForensicAnchor) -> dict[str, Any]:
    return {"anchor_id": a.anchor_id, "type": a.type, "value": a.value, "source_evidence_ids": a.source_evidence_ids}


def _timeline_dict(t: TimelineEvent) -> dict[str, Any]:
    return {"event_id": t.event_id, "description": t.description, "time_type": t.time_type, "time_start": t.time_start, "certainty": t.certainty}


def _scenario_to_dict(sc: Scenario, hyp: Hypothesis, events: list[ScenarioEvent], anchors: list[ForensicAnchor]) -> dict[str, Any]:
    return {
        "_id": sc.id,
        "hypothesis_label": hyp.hypothesis_id,
        "title": hyp.title,
        "summary": sc.summary or hyp.description,
        "cause_claim": sc.cause_claim,
        "participants": sc.participants,
        "origin": hyp.origin,
        "similar_case_patterns_used": hyp.similar_case_patterns_used,
        "injury_location": (sc.extra or {}).get("injury_location", ""),
        "events": [
            {
                "description": e.description,
                "event_type": e.event_type,
                "linked_fact_ids": e.linked_fact_ids,
                "evidence_links": e.evidence_links,
                "timing": e.timing,
                "location": e.location,
            }
            for e in events
        ],
        "unknowns": (sc.extra or {}).get("unknowns", []),
        "anchors": [_anchor_dict(a) for a in anchors],
        "state": sc.status,
        "rejection_reason": sc.rejection_reason,
        "iteration": sc.iteration_count,
    }


def _persist_scenario(
    db: Session,
    case_id: str,
    hypothesis: Hypothesis,
    draft: HypothesisDraft,
    state: str = STATE_PENDING,
    reason: str = "",
) -> Scenario:
    sc = Scenario(
        case_id=case_id,
        hypothesis_id=hypothesis.id,
        status=state,
        summary=draft.summary or draft.title,
        cause_claim=draft.cause_claim,
        participants=draft.participants,
        rejection_reason=reason,
        iteration_count=1,
        extra={"injury_location": draft.injury_location, "unknowns": draft.unknowns},
    )
    db.add(sc)
    db.flush()
    for i, ev in enumerate(draft.events):
        db.add(
            ScenarioEvent(
                scenario_id=sc.id,
                case_id=case_id,
                event_order=i,
                description=ev.description,
                event_type=ev.event_type,
                linked_fact_ids=ev.linked_fact_ids,
                evidence_links=ev.evidence_links,
                timing=ev.timing,
                location=ev.location,
            )
        )
    db.flush()
    return sc


class ReasoningEngine:
    def __init__(self) -> None:
        self.generator = InvestigativeReasoningAgent()
        self.critic = HypothesisCriticAgent()
        self.revision = HypothesisRevisionAgent()
        self.constraints = ConstraintEngine()

    def run(self, db: Session, case_id: str) -> ReasoningResult:
        result = ReasoningResult()
        facts = db.query(Fact).filter_by(case_id=case_id).all()
        timeline = db.query(TimelineEvent).filter_by(case_id=case_id).order_by(TimelineEvent.ordering_index).all()
        anchors = db.query(ForensicAnchor).filter_by(case_id=case_id).all()
        similar = db.query(SimilarCase).filter_by(case_id=case_id).order_by(SimilarCase.similarity.desc()).all()
        fact_by_id = {f.fact_id: f for f in facts}

        payload = self.generator.build_case_payload(db, case_id)
        payload["anchors"] = [_anchor_dict(a) for a in anchors]

        # ---- Initial generation ----
        if not db.query(Hypothesis).filter_by(case_id=case_id).count():
            hset = self.generator.generate(payload)
            for hd in hset.hypotheses:
                hyp = self._create_hypothesis(db, case_id, hd)
                _persist_scenario(db, case_id, hyp, hd)
            result.total_generated = len(hset.hypotheses)
            db.add(
                AuditEvent(
                    case_id=case_id,
                    action="hypothesis_generation",
                    agent=self.generator.name,
                    provider=self.generator.llm.name,
                    summary=f"Generated {len(hset.hypotheses)} candidate hypotheses",
                    extra={"provider_label": self.generator.provider_label},
                )
            )
            db.flush()

        iteration = 0
        while iteration < settings.MAX_REASONING_ITERATIONS:
            iteration += 1
            result.iterations = iteration
            pending = self._load_pending(db, case_id, anchors)
            if not pending:
                result.stopped_reason = "no pending scenarios"
                break

            new_candidates: list[tuple[str, HypothesisDraft]] = []
            for sc_dict in pending:
                self._validate(db, case_id, sc_dict, fact_by_id, result, new_candidates)

            # ---- Hypothesis expansion from failed candidates ----
            if new_candidates:
                result.expansions += len(new_candidates)
                for origin, hd in new_candidates:
                    hyp = self._create_hypothesis(db, case_id, hd, origin=origin)
                    _persist_scenario(db, case_id, hyp, hd)
                    result.total_generated += 1

            # Stopping: no new pending after this round and no expansion candidates.
            remaining_pending = self._count_pending(db, case_id)
            if not remaining_pending and not new_candidates:
                result.stopped_reason = "all candidates validated, no new material candidates"
                break
            if iteration >= settings.MAX_REASONING_ITERATIONS:
                result.stopped_reason = "max iterations safety limit reached"
                break

        # ---- Deduplicate survivors ----
        survivors = self._load_survivors(db, case_id, anchors)
        survivor_dicts = [s for _, s in survivors]
        unique, merged = deduplicate(survivor_dicts)
        for rec in merged:
            result.merged += 1
            db.add(
                AuditEvent(
                    case_id=case_id,
                    action="scenario_deduplication",
                    agent="DeduplicationEngine",
                    provider="deterministic",
                    summary=f"{rec['merged']} merged into {rec['merged_into']}",
                )
            )
        # Mark merged ones rejected.
        merged_labels = {rec["merged"] for rec in merged}
        for sc, sc_dict in survivors:
            if sc_dict["hypothesis_label"] in merged_labels:
                sc.status = STATE_REJECTED
                sc.rejection_reason = f"Deduplicated: merged into {sc_dict.get('dedup_merged', [''])[0] if sc_dict.get('dedup_merged') else 'a survivor'}"
                sc.is_survivor = False

        # ---- Score + rank surviving ----
        ranked = self._score_and_rank(db, case_id, unique, anchors, fact_by_id, result)

        # ---- Discriminating evidence for top pairs ----
        self._build_discriminating(db, case_id, ranked[:4])

        db.flush()
        return result

    # ------------------------------------------------------------------

    def _create_hypothesis(self, db: Session, case_id: str, hd: HypothesisDraft, origin: str = "") -> Hypothesis:
        hyp = Hypothesis(
            case_id=case_id,
            hypothesis_id=Ids.next_hypothesis(db, case_id),
            title=hd.title,
            description=hd.summary,
            origin=hd.origin or origin or "INITIAL",
            similar_case_patterns_used=hd.similar_case_patterns_used,
            extra={"cause_claim": hd.cause_claim},
        )
        db.add(hyp)
        db.flush()
        return hyp

    def _load_pending(self, db: Session, case_id: str, anchors: list[ForensicAnchor]) -> list[dict[str, Any]]:
        out = []
        rows = (
            db.query(Scenario, Hypothesis)
            .join(Hypothesis, Scenario.hypothesis_id == Hypothesis.id)
            .filter(Scenario.case_id == case_id, Scenario.status.in_([STATE_PENDING, STATE_VALIDATING]))
            .all()
        )
        for sc, hyp in rows:
            events = db.query(ScenarioEvent).filter_by(scenario_id=sc.id).order_by(ScenarioEvent.event_order).all()
            sc.status = STATE_VALIDATING
            out.append(_scenario_to_dict(sc, hyp, events, anchors))
        db.flush()
        return out

    def _load_survivors(self, db: Session, case_id: str, anchors: list[ForensicAnchor]) -> list[tuple[str, dict[str, Any]]]:
        out = []
        rows = (
            db.query(Scenario, Hypothesis)
            .join(Hypothesis, Scenario.hypothesis_id == Hypothesis.id)
            .filter(Scenario.case_id == case_id, Scenario.status == STATE_SURVIVING)
            .all()
        )
        for sc, hyp in rows:
            events = db.query(ScenarioEvent).filter_by(scenario_id=sc.id).order_by(ScenarioEvent.event_order).all()
            out.append((sc.id, _scenario_to_dict(sc, hyp, events, anchors)))
        return out

    def _count_pending(self, db: Session, case_id: str) -> int:
        return (
            db.query(Scenario)
            .filter(Scenario.case_id == case_id, Scenario.status.in_([STATE_PENDING, STATE_VALIDATING]))
            .count()
        )

    def _validate(
        self,
        db: Session,
        case_id: str,
        sc_dict: dict[str, Any],
        fact_by_id: dict[str, Fact],
        result: ReasoningResult,
        new_candidates: list[tuple[str, HypothesisDraft]],
    ) -> None:
        facts = list(fact_by_id.values())
        timeline = db.query(TimelineEvent).filter_by(case_id=case_id).order_by(TimelineEvent.ordering_index).all()
        anchors_orm = db.query(ForensicAnchor).filter_by(case_id=case_id).all()

        # ---- Iteration 1: constraint audit (deterministic) ----
        violations = self.constraints.check(sc_dict, anchors_orm, facts, timeline)
        hard_violations = [v for v in violations if v.severity == "HARD"]
        soft_violations = [v for v in violations if v.severity == "SOFT"]

        if hard_violations:
            self._reject(db, case_id, sc_dict, hard_violations, fact_by_id, result, new_candidates)
            return

        # ---- Evidence + forensic audit ----
        supporting, contradicting, witness_conflicts, unsupported, unknowns, inferred = self._evidence_audit(
            sc_dict, fact_by_id
        )
        anchors_satisfied = True

        # ---- Iteration 5: adversarial critic ----
        critique = self.critic.critique(
            sc_dict,
            [_anchor_dict(a) for a in anchors_orm],
            [_fact_dict(f) for f in facts],
            [_timeline_dict(t) for t in timeline],
        )
        db.add(
            AuditEvent(
                case_id=case_id,
                action="adversarial_review",
                agent=self.critic.name,
                provider=self.critic.llm.name,
                input_object_ids=[sc_dict["_id"]],
                summary=f"{critique.verdict} - {critique.summary}",
                extra={"issues": [i.model_dump() for i in critique.issues]},
            )
        )

        hard_issues = [i for i in critique.issues if i.severity == "HARD"]
        if hard_issues:
            self._reject(db, case_id, sc_dict, [ConstraintViolation(type=i.type, severity="HARD", description=i.description, constraint_ref=i.constraint) for i in hard_issues], fact_by_id, result, new_candidates)
            return

        # Fixable issues -> revise and re-check.
        fixable = [i for i in critique.issues if i.fixable]
        if fixable:
            revision = self.revision.revise(sc_dict, [i.model_dump() for i in fixable])
            if revision.reject:
                self._reject(db, case_id, sc_dict, [ConstraintViolation(type="FORENSIC", severity="HARD", description=revision.reason)], fact_by_id, result, new_candidates)
                return
            if revision.revised:
                # Persist as a new candidate (parent link preserved via origin).
                revised_hd = HypothesisDraft(
                    title=sc_dict.get("title", ""),
                    summary=revision.revised.summary or sc_dict.get("summary", ""),
                    cause_claim=sc_dict.get("cause_claim", ""),
                    participants=sc_dict.get("participants", []),
                    events=revision.revised.events,
                    unknowns=sc_dict.get("unknowns", []),
                    origin="REVISION",
                    similar_case_patterns_used=sc_dict.get("similar_case_patterns_used", []),
                    injury_location=sc_dict.get("injury_location", ""),
                )
                new_candidates.append(("REVISION", revised_hd))
                db.add(
                    AuditEvent(
                        case_id=case_id,
                        action="hypothesis_revision",
                        agent=self.revision.name,
                        provider=self.revision.llm.name,
                        input_object_ids=[sc_dict["_id"]],
                        summary=f"Revised candidate to fix fixable issues",
                    )
                )
                self._reject(db, case_id, sc_dict, [], fact_by_id, result, new_candidates, reason="superseded by revision", suppressed=True)
                return

        # Survive.
        sc = db.get(Scenario, sc_dict["_id"])
        sc.status = STATE_SURVIVING
        sc.is_survivor = True
        sc.final_verdict = (
            f"This scenario is consistent with the currently available evidence "
            f"({len(supporting)} supporting, {len(contradicting)} contradicting evidence items, "
            f"{len(hard_violations)} hard constraint violations)."
        )
        sc.extra["unknowns"] = sc_dict.get("unknowns", [])
        self._link_evidence(db, case_id, sc, supporting, contradicting)
        result.surviving += 1
        db.flush()

    def _reject(
        self,
        db: Session,
        case_id: str,
        sc_dict: dict[str, Any],
        violations: list[ConstraintViolation],
        fact_by_id: dict[str, Fact],
        result: ReasoningResult,
        new_candidates: list[tuple[str, HypothesisDraft]],
        reason: str = "",
        suppressed: bool = False,
    ) -> None:
        sc = db.get(Scenario, sc_dict["_id"])
        sc.status = STATE_REJECTED
        sc.is_survivor = False
        reason = reason or "; ".join(v.description for v in violations) or "rejected by validation"
        sc.rejection_reason = reason
        result.rejected += 1 if not suppressed else 0
        db.add(
            AuditEvent(
                case_id=case_id,
                action="scenario_rejection",
                agent="ConstraintEngine/Critic",
                provider="deterministic",
                input_object_ids=[sc_dict["_id"]],
                summary=f"Rejected: {reason[:300]}",
                extra={"violations": [v.__dict__ for v in violations]},
            )
        )
        # Expansion: a failed hypothesis may reveal new valid possibilities.
        if violations and not suppressed:
            expansion = self.generator.expand(db, case_id, sc_dict)
            if expansion.hypotheses:
                for hd in expansion.hypotheses:
                    hd.origin = "EXPANSION"
                    new_candidates.append(("EXPANSION", hd))
        db.flush()

    def _evidence_audit(
        self, sc_dict: dict[str, Any], fact_by_id: dict[str, Fact]
    ) -> tuple[set[str], set[str], list[str], list[str], list[str], list[str]]:
        supporting: set[str] = set()
        contradicting: set[str] = set()
        witness_conflicts: list[str] = []
        unsupported: list[str] = []
        unknowns: list[str] = []
        inferred: list[str] = []

        for ev in sc_dict.get("events", []):
            etype = ev.get("event_type")
            if etype in ("KNOWN", "INFERRED", "HYPOTHESIZED"):
                supporting.update(ev.get("evidence_links", []))
            if etype == "KNOWN" and not ev.get("linked_fact_ids"):
                unsupported.append(ev.get("description", ""))
            if etype == "UNKNOWN":
                unknowns.append(ev.get("description", ""))
            if etype == "INFERRED":
                inferred.append(ev.get("description", ""))
            for fid in ev.get("linked_fact_ids", []):
                fact = fact_by_id.get(fid)
                if fact:
                    supporting.update(fact.source_evidence_ids)
                    if fact.status == "CONTESTED":
                        witness_conflicts.append(fact.fact_id)
                        contradicting.update(fact.source_evidence_ids)
                    elif fact.status == "SOFT" and fact.source_type == "WITNESS_STATEMENT":
                        if etype == "KNOWN":
                            contradicting.update(fact.source_evidence_ids)
        unknowns.extend(sc_dict.get("unknowns", []))
        return supporting, contradicting, witness_conflicts, unsupported, unknowns, inferred

    def _link_evidence(self, db: Session, case_id: str, sc: Scenario, supporting: set[str], contradicting: set[str]) -> None:
        evidence_map = {e.evidence_id: e.id for e in db.query(EvidenceItem).filter_by(case_id=case_id).all()}
        for ev_id in supporting:
            if ev_id in evidence_map:
                db.add(
                    ScenarioEvidenceLink(
                        scenario_id=sc.id,
                        case_id=case_id,
                        evidence_item_id=evidence_map[ev_id],
                        link_type="SUPPORTING",
                    )
                )
        for ev_id in contradicting:
            if ev_id in evidence_map:
                db.add(
                    ScenarioEvidenceLink(
                        scenario_id=sc.id,
                        case_id=case_id,
                        evidence_item_id=evidence_map[ev_id],
                        link_type="CONTRADICTING",
                    )
                )

    def _score_and_rank(
        self, db: Session, case_id: str, survivor_dicts: list[dict[str, Any]], anchors: list[ForensicAnchor], fact_by_id: dict[str, Fact], result: ReasoningResult
    ) -> list[dict[str, Any]]:
        ranked_out: list[dict[str, Any]] = []
        for sc_dict in survivor_dicts:
            supporting, contradicting, witness_conflicts, unsupported, unknowns, inferred = self._evidence_audit(sc_dict, fact_by_id)
            anchors_satisfied = True
            scenario_injury = sc_dict.get("injury_location")
            if scenario_injury:
                for a in anchors:
                    if a.type == "INJURY_LOCATION" and (a.value or {}).get("location") and a.value["location"] != scenario_injury:
                        anchors_satisfied = False
            scored = compute_evidence_consistency_score(
                sc_dict,
                list(supporting),
                list(contradicting),
                [],
                witness_conflicts,
                unsupported,
                unknowns,
                inferred,
                anchors_satisfied,
            )
            sc = db.get(Scenario, sc_dict["_id"])
            db.add(
                ScenarioScore(
                    scenario_id=sc.id,
                    total=scored["total"],
                    breakdown=scored["breakdown"],
                )
            )
            sc_dict["score_total"] = scored["total"]
            sc_dict["score_breakdown"] = scored["breakdown"]
            sc_dict["unknown_count"] = len(unknowns)
            sc_dict["unsupported_count"] = len(unsupported)
            sc_dict["supporting_evidence"] = list(supporting)
            sc_dict["contradicting_evidence"] = list(contradicting)
            db.add(
                AuditEvent(
                    case_id=case_id,
                    action="scenario_scoring",
                    agent="ScoringEngine",
                    provider="deterministic",
                    input_object_ids=[sc.id],
                    summary=f"Evidence Consistency Score {scored['total']}/100",
                )
            )
            db.flush()
            ranked_out.append(sc_dict)

        ranked = rank_scenarios(ranked_out)
        for pos, sc_dict in enumerate(ranked, start=1):
            sc = db.get(Scenario, sc_dict["_id"])
            sc.extra["rank"] = pos
        db.add(
            AuditEvent(
                case_id=case_id,
                action="scenario_ranking",
                agent="RankingEngine",
                provider="deterministic",
                summary=f"Ranked {len(ranked)} surviving scenarios",
            )
        )
        db.flush()
        return ranked

    def _build_discriminating(self, db: Session, case_id: str, ranked: list[dict[str, Any]]) -> None:
        for i in range(len(ranked) - 1):
            a, b = ranked[i], ranked[i + 1]
            sa = set(a.get("supporting_evidence", []))
            sb = set(b.get("supporting_evidence", []))
            differing = sorted(sa ^ sb)
            if not differing:
                continue
            db.add(
                DiscriminatingEvidence(
                    case_id=case_id,
                    scenario_pair=[a.get("hypothesis_label", ""), b.get("hypothesis_label", "")],
                    shared_evidence=sorted(sa & sb),
                    differing_evidence=differing,
                    needed_evidence=[
                        "additional camera coverage of the unobserved area",
                        "weapon / object position evidence",
                        "additional forensic examination",
                        "additional witness evidence",
                        "digital location evidence",
                    ],
                    note="Potentially discriminating evidence may help distinguish these scenarios; it is not guaranteed to resolve the ambiguity.",
                )
            )