from __future__ import annotations

import time

from app.config import get_settings
from app.database import SessionLocal

settings = get_settings()


def worker_loop() -> None:
    from app.infrastructure.jobs.tasks import claim_next_job, run_job

    print(f"[worker] BAKKE worker started (poll={settings.JOB_POLL_INTERVAL_SECONDS}s)")
    while True:
        db = SessionLocal()
        try:
            job = claim_next_job(db)
            if job:
                print(f"[worker] running job {job.id} ({job.job_type})")
                job = run_job(db, job)
                print(f"[worker] job {job.id} -> {job.status}")
            db.commit()
        except Exception as exc:
            print(f"[worker] error: {exc}")
            db.rollback()
        finally:
            db.close()
        time.sleep(settings.JOB_POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    worker_loop()