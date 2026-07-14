from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, Index, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.enums import ShortlistStatus
from app.db.metadata import database_enum

if TYPE_CHECKING:
    from app.db.models.candidate import Candidate
    from app.db.models.job import JobPosting


class ShortlistEntry(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "shortlist_entries"
    __table_args__ = (
        Index("ix_shortlist_entries_created_at", "created_at"),
        UniqueConstraint("job_id", "candidate_id", name="uq_shortlist_job_candidate"),
    )

    job_id: Mapped[UUID] = mapped_column(
        ForeignKey("job_postings.id", ondelete="CASCADE"), index=True
    )
    candidate_id: Mapped[UUID] = mapped_column(
        ForeignKey("candidates.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[ShortlistStatus] = mapped_column(
        database_enum(ShortlistStatus, "shortlist_status"),
        default=ShortlistStatus.SHORTLISTED,
        index=True,
    )
    recruiter_note: Mapped[str | None] = mapped_column(Text)

    job: Mapped[JobPosting] = relationship(back_populates="shortlist_entries")
    candidate: Mapped[Candidate] = relationship(back_populates="shortlist_entries")
