"""Seed the reference-case library used for similar-case retrieval.

These are DOCUMENTED/SOLVED reference cases. They are analogical references
only and are never treated as proof for any current case.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal, init_db  # noqa: E402
from app.models import ReferenceCase  # noqa: E402
from app.adapters.providers import get_embedding_provider  # noqa: E402

REFERENCE_CASES = [
    {
        "reference_id": "SC-001",
        "title": "Reference Case 1 - Unobserved room, knife present, single entry/exit",
        "description": "A person carrying a knife entered a hallway covered by CCTV; the critical room was not covered. A victim was found deceased with a single stab wound to the right hip. The documented conclusion was that the causal sequence inside the unobserved room could not be fully reconstructed from available evidence.",
        "summary": "Blind interior room. Knife present. Injury at right hip. Entry and exit observed on camera, interior not observed.",
        "injury_pattern": ["right hip", "single stab wound"],
        "weapon_pattern": ["knife"],
        "timeline_pattern": ["entry observed", "exit observed", "uncertain event window"],
        "spatial_pattern": ["hallway covered", "room not covered", "blind camera area"],
        "witness_conflict_pattern": ["witness claimed earlier departure"],
        "evidence_gap_pattern": ["blind camera area", "no interior coverage"],
        "event_sequence": ["person enters carrying knife", "unknown events in room", "person exits", "victim found with right hip injury"],
        "conclusion": "The documented case concluded the sequence inside the room could not be determined from available evidence.",
    },
    {
        "reference_id": "SC-002",
        "title": "Reference Case 2 - Self-inflicted injury, weapon never used",
        "description": "A knife was present at the scene, but forensic analysis determined the injury was self-inflicted and the knife was not used against another person.",
        "summary": "Knife present but not used; self-inflicted injury; no other participant implicated.",
        "injury_pattern": ["single wound"],
        "weapon_pattern": ["knife"],
        "timeline_pattern": ["short event window"],
        "spatial_pattern": [],
        "witness_conflict_pattern": [],
        "evidence_gap_pattern": [],
        "event_sequence": ["person present with knife", "self-inflicted injury", "knife not used against another"],
        "conclusion": "Injury self-inflicted; knife possession did not imply use against another person.",
    },
    {
        "reference_id": "SC-003",
        "title": "Reference Case 3 - Contradicted witness timeline",
        "description": "A witness statement about a departure time conflicted with verified CCTV footage. The CCTV timeline was retained; the witness statement was treated as contested.",
        "summary": "Witness statement conflicts with CCTV timestamps. Both accounts preserved; conflict documented.",
        "injury_pattern": [],
        "weapon_pattern": [],
        "timeline_pattern": ["contested departure time"],
        "spatial_pattern": ["covered hallway"],
        "witness_conflict_pattern": ["witness departure time differs from CCTV"],
        "evidence_gap_pattern": [],
        "event_sequence": ["person visible on CCTV at recorded time", "witness claims different departure time", "conflict documented, not auto-resolved"],
        "conclusion": "Witness/CCTV conflict documented; neither account silently discarded.",
    },
]


def seed_reference_cases(force: bool = False) -> int:
    init_db()
    db = SessionLocal()
    try:
        existing = db.query(ReferenceCase).count()
        if existing and not force:
            print(f"reference library already has {existing} cases; use force=True to reseed")
            return existing
        provider = get_embedding_provider()
        added = 0
        for rc in REFERENCE_CASES:
            texts = [f"{rc['title']} {rc['summary']} {rc['conclusion']}"]
            emb = provider.embed(texts)[0]
            row = ReferenceCase(
                reference_id=rc["reference_id"],
                title=rc["title"],
                description=rc["description"],
                summary=rc["summary"],
                injury_pattern=rc["injury_pattern"],
                weapon_pattern=rc["weapon_pattern"],
                timeline_pattern=rc["timeline_pattern"],
                spatial_pattern=rc["spatial_pattern"],
                witness_conflict_pattern=rc["witness_conflict_pattern"],
                evidence_gap_pattern=rc["evidence_gap_pattern"],
                event_sequence=rc["event_sequence"],
                conclusion=rc["conclusion"],
                embedding=emb,
            )
            db.add(row)
            added += 1
        db.commit()
        print(f"seeded {added} reference cases")
        return added
    finally:
        db.close()


if __name__ == "__main__":
    seed_reference_cases(force="--force" in sys.argv)