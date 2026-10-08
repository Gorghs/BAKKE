"""Seed the fictional demonstration case and run the full pipeline.

Creates a demo case with all evidence types, seeds the reference library,
runs multimodal analysis + reasoning, and optionally generates the 3D
animated video for the top surviving scenario.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.api.deps import ensure_dev_user  # noqa: E402
from app.database import SessionLocal, init_db  # noqa: E402
from app.models import Case, EvidenceItem, GeneratedVideo, Scenario  # noqa: E402
from app.features.analysis.analysis_service import AnalysisService  # noqa: E402
from app.features.visualization.video_service import VideoService  # noqa: E402

POST_MORTEM = """POST-MORTEM REPORT - CASE PM-2026-018

Patient: unidentified adult, gender unknown.
Reported cause of death: fatal penetrating injury.
Injury location: right hip. Confirmed single penetrating wound.
The injury is located at the right hip region.
Estimated time of death: 20:00-21:00.
Exact mechanism of injury cannot be determined from the wound alone.
Cause of death was not otherwise determined to be self-inflicted or inflicted by another person.
"""

FORENSIC = """FORENSIC REPORT - CASE FR-2026-018

The hallway is covered by CCTV camera. Camera coverage of the hallway is confirmed.
The critical room has no camera coverage. The room is not covered by any CCTV.
No surveillance footage exists for the interior of the critical room.
A knife was recovered at the scene. The knife was present at the location.
Fingerprints on the knife could not be conclusively assigned.
Toxicology results are pending.
"""

INVESTIGATOR = """INVESTIGATOR REPORT - CASE IR-2026-018

Person A entered the location at approximately 20:05 carrying a knife.
Person A exited the location at approximately 20:18.
The hallway is covered by camera. The critical room is not covered by camera.
The victim was later found deceased in the critical room.
The events inside the critical room are not observed.
"""

WITNESS = """WITNESS STATEMENT - W-014

Witness B states that Person A left the building at 20:10.
The witness observed Person A departing at 20:10.
This statement conflicts with CCTV footage showing Person A visible at 20:14.
The witness did not see inside the critical room.
"""

AUDIO_TRANSCRIPT = """AUDIO TRANSCRIPT - CALL 9-1-1

Caller: There's been an incident. Someone is injured. There is a knife here.
Dispatcher: Where is the injured person?
Caller: In the back room. I don't know what happened. Please hurry.
"""

HALLWAY_IMAGE = """IMAGE DESCRIPTION - CCTV HALLWAY STILL (provided by investigator)

A hallway is visible. Person A is visible in the hallway at 20:14.
No other people are visible in the frame.
"""

CCTV_CLIP = """VIDEO DESCRIPTION - CCTV HALLWAY CLIP (provided by investigator)

Person A is visible in the hallway at 20:14 walking toward the exit.
The hallway is covered by camera; the critical room is not visible.
"""


def seed_demo(analyze: bool = True, generate_video: bool = True) -> str:
    init_db()
    db = SessionLocal()
    try:
        user = ensure_dev_user(db)
        db.commit()

        from scripts.seed_reference_cases import seed_reference_cases

        seed_reference_cases(force=False)

        case = Case(
            owner_id=user.id,
            name="Demo Case: Knife / Right Hip Injury (Unobserved Room)",
            description=(
                "Fictional demonstration case. Person A entered carrying a knife. "
                "The victim was later found deceased. The critical room has no camera coverage. "
                "Post-mortem reports the injury at the right hip."
            ),
            tags=["demo", "homicide", "knife", "blind-camera-area"],
        )
        db.add(case)
        db.flush()

        evidence_specs = [
            ("POST_MORTEM_REPORT", "Post-mortem report PM-2026-018", POST_MORTEM, ""),
            ("FORENSIC_REPORT", "Forensic report FR-2026-018", FORENSIC, ""),
            ("INVESTIGATOR_REPORT", "Investigator report IR-2026-018", INVESTIGATOR, ""),
            ("WITNESS_STATEMENT", "Witness statement W-014", WITNESS, ""),
            ("AUDIO", "911 call recording (transcript attached)", "", AUDIO_TRANSCRIPT),
            ("IMAGE", "Hallway CCTV still", "", HALLWAY_IMAGE),
            ("VIDEO", "Hallway CCTV clip", "", CCTV_CLIP),
        ]
        for i, (itype, title, text, raw) in enumerate(evidence_specs, start=1):
            ev = EvidenceItem(
                case_id=case.id,
                evidence_id=f"E-{i:03d}",
                item_type=itype,
                title=title,
                description=title,
                status="UPLOADED",
                raw_text=raw or text,
                extra={"evidence_type": itype},
            )
            db.add(ev)
        case.evidence_count = len(evidence_specs)
        db.commit()
        print(f"case {case.id} created with {case.evidence_count} evidence items")

        if analyze:
            print("running analysis pipeline...")
            svc = AnalysisService()
            result = svc.analyze_case(db, case.id)
            print(f"analysis result: {result}")
            db.commit()

        if generate_video:
            survivors = (
                db.query(Scenario)
                .filter_by(case_id=case.id, is_survivor=True)
                .all()
            )
            top = survivors[0] if survivors else None
            if top:
                print(f"generating 3D animated video for {top.id}...")
                video = GeneratedVideo(case_id=case.id, scenario_id=top.id, status="PENDING")
                db.add(video)
                db.flush()
                from app.models import VideoScenarioSpec

                VideoService().generate_video(db, top, video)
                db.commit()
                print(f"video status: {video.status} -> {video.video_path}")
            else:
                print("no surviving scenario; skipping video generation")

        return case.id
    finally:
        db.close()


if __name__ == "__main__":
    case_id = seed_demo(analyze="--no-analyze" not in sys.argv, generate_video="--no-video" not in sys.argv)
    print(f"demo case id: {case_id}")