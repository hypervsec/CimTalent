from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import CheckConstraint, Float, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.enums import (
    JobSource,
    JobStatus,
    RequirementImportance,
    RequirementSource,
    RequirementType,
)
from app.db.metadata import database_enum, mutable_json_list

if TYPE_CHECKING:
    from app.db.models.matching import CandidateMatch
    from app.db.models.search import SearchQuery
    from app.db.models.shortlist import ShortlistEntry


class JobPosting(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "job_postings"
    __table_args__ = (
        Index("ix_job_postings_created_at", "created_at"),
        CheckConstraint("min_experience_years >= 0", name="min_experience_nonnegative"),
        CheckConstraint("max_experience_years >= 0", name="max_experience_nonnegative"),
        CheckConstraint(
            "max_experience_years IS NULL OR min_experience_years IS NULL "
            "OR max_experience_years >= min_experience_years",
            name="experience_range_valid",
        ),
    )

    source: Mapped[JobSource] = mapped_column(database_enum(JobSource, "job_source"), index=True)
    source_url: Mapped[str | None] = mapped_column(String(2048))
    company_name: Mapped[str] = mapped_column(String(255), index=True)
    title: Mapped[str] = mapped_column(String(255), index=True)
    description_raw: Mapped[str] = mapped_column(Text)
    description_clean: Mapped[str | None] = mapped_column(Text)
    location_raw: Mapped[str | None] = mapped_column(String(500))
    city: Mapped[str | None] = mapped_column(String(120), index=True)
    country: Mapped[str | None] = mapped_column(String(120))
    employment_type: Mapped[str | None] = mapped_column(String(120))
    seniority_level: Mapped[str | None] = mapped_column(String(120))
    min_experience_years: Mapped[float | None] = mapped_column(Float)
    max_experience_years: Mapped[float | None] = mapped_column(Float)
    education_requirements: Mapped[list[object]] = mapped_column(mutable_json_list(), default=list)
    required_skills: Mapped[list[object]] = mapped_column(mutable_json_list(), default=list)
    preferred_skills: Mapped[list[object]] = mapped_column(mutable_json_list(), default=list)
    languages: Mapped[list[object]] = mapped_column(mutable_json_list(), default=list)
    certifications: Mapped[list[object]] = mapped_column(mutable_json_list(), default=list)
    keywords_tr: Mapped[list[object]] = mapped_column(mutable_json_list(), default=list)
    keywords_en: Mapped[list[object]] = mapped_column(mutable_json_list(), default=list)
    status: Mapped[JobStatus] = mapped_column(
        database_enum(JobStatus, "job_status"), default=JobStatus.DRAFT, index=True
    )

    requirements: Mapped[list[JobRequirement]] = relationship(
        back_populates="job", cascade="all, delete-orphan", passive_deletes=True
    )
    search_queries: Mapped[list[SearchQuery]] = relationship(
        back_populates="job", cascade="all, delete-orphan", passive_deletes=True
    )
    matches: Mapped[list[CandidateMatch]] = relationship(
        back_populates="job", cascade="all, delete-orphan", passive_deletes=True
    )
    shortlist_entries: Mapped[list[ShortlistEntry]] = relationship(
        back_populates="job", cascade="all, delete-orphan", passive_deletes=True
    )

    def __repr__(self) -> str:
        return f"<JobPosting id={self.id} title={self.title!r} status={self.status.value!r}>"


class JobRequirement(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "job_requirements"
    __table_args__ = (
        CheckConstraint("weight >= 0", name="weight_nonnegative"),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="confidence_range"),
    )

    job_id: Mapped[UUID] = mapped_column(
        ForeignKey("job_postings.id", ondelete="CASCADE"), index=True
    )
    type: Mapped[RequirementType] = mapped_column(
        database_enum(RequirementType, "requirement_type"), index=True
    )
    raw_value: Mapped[str] = mapped_column(String(1000))
    normalized_value: Mapped[str] = mapped_column(String(500), index=True)
    importance: Mapped[RequirementImportance] = mapped_column(
        database_enum(RequirementImportance, "requirement_importance"), index=True
    )
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    source: Mapped[RequirementSource] = mapped_column(
        database_enum(RequirementSource, "requirement_source")
    )

    job: Mapped[JobPosting] = relationship(back_populates="requirements")
