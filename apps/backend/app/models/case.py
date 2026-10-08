from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, JsonType, TimestampMixin, gen_uuid


class Case(Base, TimestampMixin):
    __tablename__ = "cases"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=gen_uuid)
    owner_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(String(4000), default="")
    status: Mapped[str] = mapped_column(String(40), default="DRAFT")  # DRAFT/ANALYZING/ANALYZED/ERROR
    tags: Mapped[list] = mapped_column(JsonType, default=list)
    evidence_count: Mapped[int] = mapped_column(Integer, default=0)

    owner: Mapped["User"] = relationship()  # noqa: F821
