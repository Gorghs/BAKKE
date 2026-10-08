from __future__ import annotations

import logging
import time

from app.config import get_settings
from app.database import SessionLocal

logger = logging.getLogger(__name__)

settings = get_settings()


def worker_loop() -> None:
    from app.infrastructure.jobs.tasks import claim_next_job, run_job

    logger.info("BAKKE worker started (poll=%ss)", settings.JOB_POLL_INTERVAL_SECONDS)
    while True:
        db = SessionLocal()
        try:
            job = claim_next_job(db)
            if job:
                logger.info("running job %s (%s) case=%s", job.id, job.job_type, job.case_id)
                job = run_job(db, job)
                logger.info("job %s -> %s", job.id, job.status)
            db.commit()
        except Exception:
            logger.exception("worker iteration failed")
            db.rollback()
        finally:
            db.close()
        time.sleep(settings.JOB_POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    worker_loop()
