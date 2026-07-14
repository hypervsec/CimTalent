from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import CheckConstraint, Float, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.metadata import mutable_json_list

if TYPE_CHECKING:
    from app.db.models.candidate import Candidate
    from app.db.models.job import JobPosting

SCORE_COLUMNS = (
    "total_score",
    "title_score",
    "skill_score",
    "experience_score",
    "industry_score",
    "education_score",
    "location_score",
    "language_score",
    "certification_score",
    "semantic_score",
)


class CandidateMatch(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "candidate_matches"
    __table_args__ = (
        Index("ix_candidate_matches_created_at", "created_at"),
        *(
            CheckConstraint(
                f"{column} IS NULL OR ({column} >= 0 AND {column} <= 100)",
                name=f"{column}_range",
            )
            for column in SCORE_COLUMNS
        ),
        UniqueConstraint("job_id", "candidate_id", name="uq_candidate_match_job_candidate"),
    )

    job_id: Mapped[UUID] = mapped_column(
        ForeignKey("job_postings.id", ondelete="CASCADE"), index=True
    )
    candidate_id: Mapped[UUID] = mapped_column(
        ForeignKey("candidates.id", ondelete="CASCADE"), index=True
    )
    total_score: Mapped[float] = mapped_column(Float, index=True)
    title_score: Mapped[float] = mapped_column(Float)
    skill_score: Mapped[float] = mapped_column(Float)
    experience_score: Mapped[float] = mapped_column(Float)
    industry_score: Mapped[float] = mapped_column(Float)
    education_score: Mapped[float] = mapped_column(Float)
    location_score: Mapped[float] = mapped_column(Float)
    language_score: Mapped[float] = mapped_column(Float)
    certification_score: Mapped[float] = mapped_column(Float)
    semantic_score: Mapped[float | None] = mapped_column(Float)
    matched_requirements: Mapped[list[object]] = mapped_column(mutable_json_list(), default=list)
    missing_requirements: Mapped[list[object]] = mapped_column(mutable_json_list(), default=list)
    uncertain_requirements: Mapped[list[object]] = mapped_column(mutable_json_list(), default=list)
    explanation: Mapped[str | None] = mapped_column(Text)
    score_version: Mapped[str] = mapped_column(String(50))

    job: Mapped[JobPosting] = relationship(back_populates="matches")
    candidate: Mapped[Candidate] = relationship(back_populates="matches")
