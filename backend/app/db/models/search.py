from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
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
from app.db.enums import SearchLanguage, SearchSource, SearchStatus
from app.db.metadata import database_enum, mutable_json_list

if TYPE_CHECKING:
    from app.db.models.candidate import Candidate
    from app.db.models.job import JobPosting


class SearchQuery(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "search_queries"
    __table_args__ = (
        Index("ix_search_queries_created_at", "created_at"),
        Index("ix_search_queries_normalized_query_key", "normalized_query_key"),
        CheckConstraint(
            "precision_level IS NULL OR precision_level BETWEEN 1 AND 5",
            name="precision_level_range",
        ),
        CheckConstraint("result_count >= 0", name="result_count_nonnegative"),
        UniqueConstraint(
            "job_id",
            "normalized_query_key",
            name="uq_search_queries_job_normalized_key",
        ),
    )

    job_id: Mapped[UUID] = mapped_column(
        ForeignKey("job_postings.id", ondelete="CASCADE"), index=True
    )
    source: Mapped[SearchSource] = mapped_column(
        database_enum(SearchSource, "search_source"), index=True
    )
    language: Mapped[SearchLanguage] = mapped_column(
        database_enum(SearchLanguage, "search_language"), index=True
    )
    query_text: Mapped[str] = mapped_column(Text)
    normalized_query_key: Mapped[str] = mapped_column(String(1000))
    query_type: Mapped[str | None] = mapped_column(String(100))
    precision_level: Mapped[int | None] = mapped_column(Integer)
    expected_intent: Mapped[str | None] = mapped_column(String(255))
    included_titles: Mapped[list[object]] = mapped_column(mutable_json_list(), default=list)
    included_skills: Mapped[list[object]] = mapped_column(mutable_json_list(), default=list)
    included_locations: Mapped[list[object]] = mapped_column(mutable_json_list(), default=list)
    status: Mapped[SearchStatus] = mapped_column(
        database_enum(SearchStatus, "search_status"), default=SearchStatus.DRAFT, index=True
    )
    result_count: Mapped[int] = mapped_column(Integer, default=0)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    job: Mapped[JobPosting] = relationship(back_populates="search_queries")
    results: Mapped[list[SearchResult]] = relationship(
        back_populates="search_query", cascade="all, delete-orphan", passive_deletes=True
    )


class SearchResult(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "search_results"
    __table_args__ = (
        CheckConstraint("result_rank IS NULL OR result_rank >= 1", name="result_rank_positive"),
        CheckConstraint(
            "pre_score IS NULL OR (pre_score >= 0 AND pre_score <= 100)",
            name="pre_score_range",
        ),
        UniqueConstraint("search_query_id", "normalized_url", name="uq_search_result_query_url"),
    )

    search_query_id: Mapped[UUID] = mapped_column(
        ForeignKey("search_queries.id", ondelete="CASCADE"), index=True
    )
    candidate_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("candidates.id", ondelete="SET NULL"), index=True
    )
    source_url: Mapped[str] = mapped_column(String(2048))
    normalized_url: Mapped[str] = mapped_column(String(2048), index=True)
    source_domain: Mapped[str | None] = mapped_column(String(255), index=True)
    title: Mapped[str | None] = mapped_column(String(1000))
    snippet: Mapped[str | None] = mapped_column(Text)
    displayed_name: Mapped[str | None] = mapped_column(String(255))
    displayed_headline: Mapped[str | None] = mapped_column(String(1000))
    displayed_location: Mapped[str | None] = mapped_column(String(500))
    result_rank: Mapped[int | None] = mapped_column(Integer)
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    duplicate_of_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("search_results.id", ondelete="SET NULL"), index=True
    )
    pre_score: Mapped[float | None] = mapped_column(Float, index=True)
    discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, index=True
    )

    search_query: Mapped[SearchQuery] = relationship(back_populates="results")
    candidate: Mapped[Candidate | None] = relationship(back_populates="search_results")
    duplicate_of: Mapped[SearchResult | None] = relationship(
        back_populates="duplicates", foreign_keys=[duplicate_of_id], remote_side="SearchResult.id"
    )
    duplicates: Mapped[list[SearchResult]] = relationship(
        back_populates="duplicate_of", foreign_keys=[duplicate_of_id], passive_deletes=True
    )
