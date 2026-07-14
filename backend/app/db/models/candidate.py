from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utc_now
from app.db.enums import CandidateProfileStatus, CandidateSkillSource, CandidateSource
from app.db.metadata import database_enum, mutable_json_dict, mutable_json_list
from app.domain.enrichment.enums import (
    CandidateEnrichmentStatus,
    EnrichmentMode,
    EnrichmentProvider,
)

if TYPE_CHECKING:
    from app.db.models.matching import CandidateMatch
    from app.db.models.search import SearchResult
    from app.db.models.shortlist import ShortlistEntry


class Candidate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "candidates"
    __table_args__ = (
        Index("ix_candidates_created_at", "created_at"),
        CheckConstraint(
            "total_experience_months IS NULL OR total_experience_months >= 0",
            name="total_experience_nonnegative",
        ),
        CheckConstraint(
            "data_quality_score >= 0 AND data_quality_score <= 100",
            name="data_quality_score_range",
        ),
    )

    primary_profile_url: Mapped[str | None] = mapped_column(String(2048))
    normalized_profile_url: Mapped[str | None] = mapped_column(
        String(2048), unique=True, index=True
    )
    profile_slug: Mapped[str | None] = mapped_column(String(255), index=True)
    source: Mapped[CandidateSource] = mapped_column(
        database_enum(CandidateSource, "candidate_source"), index=True
    )
    full_name: Mapped[str | None] = mapped_column(String(255), index=True)
    headline: Mapped[str | None] = mapped_column(String(1000))
    about: Mapped[str | None] = mapped_column(Text)
    discovery_title: Mapped[str | None] = mapped_column(String(1000))
    discovery_snippet: Mapped[str | None] = mapped_column(Text)
    location_raw: Mapped[str | None] = mapped_column(String(500))
    city: Mapped[str | None] = mapped_column(String(120), index=True)
    country: Mapped[str | None] = mapped_column(String(120))
    current_title: Mapped[str | None] = mapped_column(String(255), index=True)
    current_company: Mapped[str | None] = mapped_column(String(255), index=True)
    total_experience_months: Mapped[int | None] = mapped_column(Integer)
    open_to_work: Mapped[bool | None] = mapped_column(Boolean)
    profile_status: Mapped[CandidateProfileStatus] = mapped_column(
        database_enum(CandidateProfileStatus, "candidate_profile_status"),
        default=CandidateProfileStatus.DISCOVERED,
        index=True,
    )
    data_quality_score: Mapped[float] = mapped_column(Float, default=0.0, index=True)
    last_scraped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    experiences: Mapped[list[CandidateExperience]] = relationship(
        back_populates="candidate",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="CandidateExperience.sort_order",
    )
    educations: Mapped[list[CandidateEducation]] = relationship(
        back_populates="candidate",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="CandidateEducation.sort_order",
    )
    skills: Mapped[list[CandidateSkill]] = relationship(
        back_populates="candidate", cascade="all, delete-orphan", passive_deletes=True
    )
    certifications: Mapped[list[CandidateCertification]] = relationship(
        back_populates="candidate", cascade="all, delete-orphan", passive_deletes=True
    )
    languages: Mapped[list[CandidateLanguage]] = relationship(
        back_populates="candidate", cascade="all, delete-orphan", passive_deletes=True
    )
    matches: Mapped[list[CandidateMatch]] = relationship(
        back_populates="candidate", cascade="all, delete-orphan", passive_deletes=True
    )
    shortlist_entries: Mapped[list[ShortlistEntry]] = relationship(
        back_populates="candidate", cascade="all, delete-orphan", passive_deletes=True
    )
    search_results: Mapped[list[SearchResult]] = relationship(
        back_populates="candidate", passive_deletes=True
    )
    merge_audits: Mapped[list[CandidateMergeAudit]] = relationship(
        back_populates="target_candidate", passive_deletes=True
    )
    enrichment_runs: Mapped[list[CandidateEnrichmentRun]] = relationship(
        back_populates="candidate",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="CandidateEnrichmentRun.created_at.desc()",
    )

    @property
    def experience_years(self) -> float | None:
        if self.total_experience_months is None:
            return None
        return round(self.total_experience_months / 12, 2)

    @property
    def has_complete_profile(self) -> bool:
        return all(
            (self.full_name, self.headline, self.current_title, self.current_company)
        ) and bool(self.experiences)

    def __repr__(self) -> str:
        return (
            f"<Candidate id={self.id} full_name={self.full_name!r} "
            f"status={self.profile_status.value!r}>"
        )


class CandidateExperience(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "candidate_experiences"
    __table_args__ = (
        CheckConstraint(
            "duration_months IS NULL OR duration_months >= 0",
            name="duration_months_nonnegative",
        ),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="confidence_range"),
        CheckConstraint("sort_order >= 0", name="sort_order_nonnegative"),
        CheckConstraint(
            "end_date IS NULL OR start_date IS NULL OR end_date >= start_date",
            name="date_range_valid",
        ),
        Index("ix_candidate_experience_identity", "candidate_id", "source", "external_key"),
    )

    candidate_id: Mapped[UUID] = mapped_column(
        ForeignKey("candidates.id", ondelete="CASCADE"), index=True
    )
    external_key: Mapped[str | None] = mapped_column(String(500))
    source: Mapped[str | None] = mapped_column(String(120))
    position_title_raw: Mapped[str] = mapped_column(String(500))
    position_title_normalized: Mapped[str | None] = mapped_column(String(255), index=True)
    company_name: Mapped[str | None] = mapped_column(String(255), index=True)
    company_url: Mapped[str | None] = mapped_column(String(2048))
    employment_type: Mapped[str | None] = mapped_column(String(120))
    location: Mapped[str | None] = mapped_column(String(500))
    start_date: Mapped[date | None] = mapped_column(Date, index=True)
    end_date: Mapped[date | None] = mapped_column(Date)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    duration_months: Mapped[int | None] = mapped_column(Integer)
    description: Mapped[str | None] = mapped_column(Text)
    skills_detected: Mapped[list[object]] = mapped_column(mutable_json_list(), default=list)
    industry_detected: Mapped[str | None] = mapped_column(String(255))
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    candidate: Mapped[Candidate] = relationship(back_populates="experiences")


class CandidateEducation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "candidate_educations"
    __table_args__ = (
        CheckConstraint(
            "start_year IS NULL OR start_year BETWEEN 1900 AND 2100", name="start_year_range"
        ),
        CheckConstraint(
            "end_year IS NULL OR end_year BETWEEN 1900 AND 2100", name="end_year_range"
        ),
        CheckConstraint(
            "end_year IS NULL OR start_year IS NULL OR end_year >= start_year",
            name="year_range_valid",
        ),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="confidence_range"),
        CheckConstraint("sort_order >= 0", name="sort_order_nonnegative"),
        Index("ix_candidate_education_identity", "candidate_id", "source", "external_key"),
    )

    candidate_id: Mapped[UUID] = mapped_column(
        ForeignKey("candidates.id", ondelete="CASCADE"), index=True
    )
    external_key: Mapped[str | None] = mapped_column(String(500))
    source: Mapped[str | None] = mapped_column(String(120))
    institution_name: Mapped[str] = mapped_column(String(500), index=True)
    degree: Mapped[str | None] = mapped_column(String(255))
    field_of_study: Mapped[str | None] = mapped_column(String(255))
    field_of_study_normalized: Mapped[str | None] = mapped_column(String(255), index=True)
    start_year: Mapped[int | None] = mapped_column(Integer)
    end_year: Mapped[int | None] = mapped_column(Integer, index=True)
    grade: Mapped[str | None] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    candidate: Mapped[Candidate] = relationship(back_populates="educations")


class CandidateSkill(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "candidate_skills"
    __table_args__ = (
        CheckConstraint(
            "endorsement_count IS NULL OR endorsement_count >= 0",
            name="endorsement_count_nonnegative",
        ),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="confidence_range"),
        UniqueConstraint(
            "candidate_id", "normalized_name", "source", name="uq_candidate_skill_source"
        ),
    )

    candidate_id: Mapped[UUID] = mapped_column(
        ForeignKey("candidates.id", ondelete="CASCADE"), index=True
    )
    raw_name: Mapped[str] = mapped_column(String(255))
    normalized_name: Mapped[str] = mapped_column(String(255), index=True)
    category: Mapped[str | None] = mapped_column(String(120), index=True)
    endorsement_count: Mapped[int | None] = mapped_column(Integer)
    source: Mapped[CandidateSkillSource] = mapped_column(
        database_enum(CandidateSkillSource, "candidate_skill_source"), index=True
    )
    confidence: Mapped[float] = mapped_column(Float, default=1.0)

    candidate: Mapped[Candidate] = relationship(back_populates="skills")


class CandidateCertification(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "candidate_certifications"
    __table_args__ = (
        CheckConstraint(
            "expiration_date IS NULL OR issue_date IS NULL OR expiration_date >= issue_date",
            name="date_range_valid",
        ),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="confidence_range"),
        Index("ix_candidate_certification_identity", "candidate_id", "source", "external_key"),
    )

    candidate_id: Mapped[UUID] = mapped_column(
        ForeignKey("candidates.id", ondelete="CASCADE"), index=True
    )
    external_key: Mapped[str | None] = mapped_column(String(500))
    source: Mapped[str | None] = mapped_column(String(120))
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    name: Mapped[str] = mapped_column(String(500), index=True)
    issuer: Mapped[str | None] = mapped_column(String(255), index=True)
    issue_date: Mapped[date | None] = mapped_column(Date)
    expiration_date: Mapped[date | None] = mapped_column(Date)
    credential_id: Mapped[str | None] = mapped_column(String(255))
    credential_url: Mapped[str | None] = mapped_column(String(2048))

    candidate: Mapped[Candidate] = relationship(back_populates="certifications")


class CandidateLanguage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "candidate_languages"
    __table_args__ = (
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="confidence_range"),
        UniqueConstraint("candidate_id", "language_normalized", name="uq_candidate_language"),
    )

    candidate_id: Mapped[UUID] = mapped_column(
        ForeignKey("candidates.id", ondelete="CASCADE"), index=True
    )
    source: Mapped[str | None] = mapped_column(String(120))
    language: Mapped[str] = mapped_column(String(120))
    language_normalized: Mapped[str] = mapped_column(String(120), index=True)
    proficiency: Mapped[str | None] = mapped_column(String(120))
    confidence: Mapped[float] = mapped_column(Float, default=1.0)

    candidate: Mapped[Candidate] = relationship(back_populates="languages")


class CandidateEnrichmentRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "candidate_enrichment_runs"
    __table_args__ = (
        CheckConstraint(
            "data_quality_before >= 0 AND data_quality_before <= 100",
            name="quality_before_range",
        ),
        CheckConstraint(
            "data_quality_after IS NULL OR (data_quality_after >= 0 AND data_quality_after <= 100)",
            name="quality_after_range",
        ),
        CheckConstraint(
            "completed_at IS NULL OR started_at IS NULL OR completed_at >= started_at",
            name="date_range_valid",
        ),
        CheckConstraint(
            "created_experience_count >= 0 AND updated_experience_count >= 0 "
            "AND deleted_experience_count >= 0 AND created_education_count >= 0 "
            "AND updated_education_count >= 0 AND deleted_education_count >= 0 "
            "AND created_skill_count >= 0 AND updated_skill_count >= 0 "
            "AND deleted_skill_count >= 0 AND created_certification_count >= 0 "
            "AND updated_certification_count >= 0 AND deleted_certification_count >= 0 "
            "AND created_language_count >= 0 AND updated_language_count >= 0 "
            "AND deleted_language_count >= 0",
            name="counts_nonnegative",
        ),
        Index("ix_candidate_enrichment_runs_created_at", "created_at"),
    )

    candidate_id: Mapped[UUID] = mapped_column(
        ForeignKey("candidates.id", ondelete="CASCADE"), index=True
    )
    provider: Mapped[EnrichmentProvider] = mapped_column(
        database_enum(EnrichmentProvider, "enrichment_provider"), index=True
    )
    mode: Mapped[EnrichmentMode] = mapped_column(
        database_enum(EnrichmentMode, "enrichment_mode"), index=True
    )
    status: Mapped[CandidateEnrichmentStatus] = mapped_column(
        database_enum(CandidateEnrichmentStatus, "candidate_enrichment_status"), index=True
    )
    source_url: Mapped[str | None] = mapped_column(String(2048))
    parser_version: Mapped[str | None] = mapped_column(String(100))
    requested_sections: Mapped[list[object]] = mapped_column(mutable_json_list(), default=list)
    completed_sections: Mapped[list[object]] = mapped_column(mutable_json_list(), default=list)
    warning_codes: Mapped[list[object]] = mapped_column(mutable_json_list(), default=list)
    error_codes: Mapped[list[object]] = mapped_column(mutable_json_list(), default=list)
    input_summary: Mapped[dict[str, object]] = mapped_column(mutable_json_dict(), default=dict)
    result_summary: Mapped[dict[str, object]] = mapped_column(mutable_json_dict(), default=dict)
    data_quality_before: Mapped[float] = mapped_column(Float, default=0.0)
    data_quality_after: Mapped[float | None] = mapped_column(Float)
    created_experience_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_experience_count: Mapped[int] = mapped_column(Integer, default=0)
    deleted_experience_count: Mapped[int] = mapped_column(Integer, default=0)
    created_education_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_education_count: Mapped[int] = mapped_column(Integer, default=0)
    deleted_education_count: Mapped[int] = mapped_column(Integer, default=0)
    created_skill_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_skill_count: Mapped[int] = mapped_column(Integer, default=0)
    deleted_skill_count: Mapped[int] = mapped_column(Integer, default=0)
    created_certification_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_certification_count: Mapped[int] = mapped_column(Integer, default=0)
    deleted_certification_count: Mapped[int] = mapped_column(Integer, default=0)
    created_language_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_language_count: Mapped[int] = mapped_column(Integer, default=0)
    deleted_language_count: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    candidate: Mapped[Candidate] = relationship(back_populates="enrichment_runs")


class CandidateMergeAudit(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "candidate_merge_audits"
    __table_args__ = (
        CheckConstraint(
            "moved_search_result_count >= 0 AND moved_experience_count >= 0 "
            "AND moved_education_count >= 0 AND moved_skill_count >= 0 "
            "AND moved_certification_count >= 0 AND moved_language_count >= 0",
            name="moved_counts_nonnegative",
        ),
    )

    target_candidate_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("candidates.id", ondelete="SET NULL"), index=True
    )
    source_candidate_ids: Mapped[list[object]] = mapped_column(mutable_json_list())
    field_strategy: Mapped[str] = mapped_column(String(50))
    merged_fields: Mapped[dict[str, object]] = mapped_column(mutable_json_dict())
    conflicts: Mapped[list[object]] = mapped_column(mutable_json_list())
    moved_search_result_count: Mapped[int] = mapped_column(Integer, default=0)
    moved_experience_count: Mapped[int] = mapped_column(Integer, default=0)
    moved_education_count: Mapped[int] = mapped_column(Integer, default=0)
    moved_skill_count: Mapped[int] = mapped_column(Integer, default=0)
    moved_certification_count: Mapped[int] = mapped_column(Integer, default=0)
    moved_language_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    target_candidate: Mapped[Candidate | None] = relationship(back_populates="merge_audits")
