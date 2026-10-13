from __future__ import annotations

import time

from app.config import get_settings
from app.database import SessionLocal

settings = get_settings()


def worker_loop() -> None:
    from app.jobs.supervisor import SUPERVISOR_INTERVAL_SECONDS, supervise
    from app.jobs.tasks import claim_next_job, run_job

    print(f"[worker] BAKKE worker started (poll={settings.JOB_POLL_INTERVAL_SECONDS}s)")
    last_supervise = 0.0
    while True:
        db = SessionLocal()
        try:
            job = claim_next_job(db)
            if job:
                print(f"[worker] running job {job.id} ({job.job_type})")
                job = run_job(db, job)
                print(f"[worker] job {job.id} -> {job.status}")
            db.commit()
            if time.monotonic() - last_supervise >= SUPERVISOR_INTERVAL_SECONDS:
                last_supervise = time.monotonic()
                report = supervise(db)
                db.commit()
                if report["requeued"] or report["failed"] or report["stale_pending"]:
                    print(f"[worker] supervisor: {report}")
        except Exception as exc:
            print(f"[worker] error: {exc}")
            db.rollback()
        finally:
            db.close()
        time.sleep(settings.JOB_POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    worker_loop()