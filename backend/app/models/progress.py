from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class JobProgress(Base):
    """Live progress heartbeat for a running job.

    A worker runs each job inside one long, uncommitted transaction, so
    anything it writes to the job row stays invisible until the job ends
    (and locks the row in the meantime). This row is written from a separate
    session, so the API can report live progress while the job still runs.

    job_id is a plain key, not a foreign key: an FK insert would take a lock
    on the job row that the running transaction already holds.
    """

    __tablename__ = "job_progress"

    job_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    stage: Mapped[str] = mapped_column(String(200), default="")
    percent: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
