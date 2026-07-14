from __future__ import annotations

from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.db.enums import CandidateProfileStatus, CandidateSource, SearchLanguage
from app.domain.candidates.types import (
    CandidateDiscoveryAction,
    CandidateFieldStrategy,
    CandidateMatchedBy,
)
from app.schemas.common import UtcDateTime

IDENTITY_FIELDS = ("primary_profile_url", "full_name", "discovery_title")
TEXT_FIELDS = (
    "primary_profile_url",
    "full_name",
    "headline",
    "about",
    "discovery_title",
    "discovery_snippet",
    "location_raw",
    "city",
    "country",
    "current_title",
    "current_company",
)


class CandidateCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: CandidateSource = CandidateSource.MANUAL
    primary_profile_url: str | None = Field(default=None, max_length=2048)
    full_name: str | None = Field(default=None, max_length=255)
    headline: str | None = Field(default=None, max_length=1000)
    about: str | None = Field(default=None, max_length=50_000)
    discovery_title: str | None = Field(default=None, max_length=1000)
    discovery_snippet: str | None = Field(default=None, max_length=10_000)
    location_raw: str | None = Field(default=None, max_length=500)
    city: str | None = Field(default=None, max_length=120)
    country: str | None = Field(default=None, max_length=120)
    current_title: str | None = Field(default=None, max_length=255)
    current_company: str | None = Field(default=None, max_length=255)
    total_experience_months: int | None = Field(default=None, ge=0)
    open_to_work: bool | None = None
    profile_status: CandidateProfileStatus = CandidateProfileStatus.DISCOVERED

    @field_validator(*TEXT_FIELDS, mode="before")
    @classmethod
    def trim_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_candidate(self) -> Self:
        if not any(getattr(self, field_name) for field_name in IDENTITY_FIELDS):
            raise ValueError("At least one candidate identity field is required.")
        if self.source not in {
            CandidateSource.MANUAL,
            CandidateSource.IMPORTED,
            CandidateSource.DEMO,
        }:
            raise ValueError("Manual create supports manual, imported, or demo source.")
        return self


class CandidateUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    primary_profile_url: str | None = Field(default=None, max_length=2048)
    full_name: str | None = Field(default=None, max_length=255)
    headline: str | None = Field(default=None, max_length=1000)
    about: str | None = Field(default=None, max_length=50_000)
    discovery_title: str | None = Field(default=None, max_length=1000)
    discovery_snippet: str | None = Field(default=None, max_length=10_000)
    location_raw: str | None = Field(default=None, max_length=500)
    city: str | None = Field(default=None, max_length=120)
    country: str | None = Field(default=None, max_length=120)
    current_title: str | None = Field(default=None, max_length=255)
    current_company: str | None = Field(default=None, max_length=255)
    total_experience_months: int | None = Field(default=None, ge=0)
    open_to_work: bool | None = None
    profile_status: CandidateProfileStatus | None = None

    @field_validator(*TEXT_FIELDS, mode="before")
    @classmethod
    def trim_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class CandidateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    primary_profile_url: str | None
    normalized_profile_url: str | None
    profile_slug: str | None
    source: CandidateSource
    full_name: str | None
    headline: str | None
    about: str | None
    discovery_title: str | None
    discovery_snippet: str | None
    location_raw: str | None
    city: str | None
    country: str | None
    current_title: str | None
    current_company: str | None
    total_experience_months: int | None
    experience_years: float | None
    open_to_work: bool | None
    profile_status: CandidateProfileStatus
    data_quality_score: float
    last_scraped_at: UtcDateTime | None
    created_at: UtcDateTime
    updated_at: UtcDateTime
    experience_count: int = 0
    education_count: int = 0
    skill_count: int = 0
    certification_count: int = 0
    language_count: int = 0
    search_result_count: int = 0
    match_count: int = 0
    shortlist_count: int = 0


class CandidateListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    full_name: str | None
    headline: str | None
    current_title: str | None
    current_company: str | None
    city: str | None
    country: str | None
    source: CandidateSource
    profile_status: CandidateProfileStatus
    data_quality_score: float
    total_experience_months: int | None
    primary_profile_url: str | None
    search_result_count: int = 0
    created_at: UtcDateTime
    updated_at: UtcDateTime


class CandidateSearchResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    source_url: str
    normalized_url: str
    source_domain: str | None
    title: str | None
    snippet: str | None
    displayed_name: str | None
    displayed_headline: str | None
    displayed_location: str | None
    discovered_at: UtcDateTime
    query_id: UUID
    query_text: str
    query_language: SearchLanguage
    job_id: UUID
    job_title: str


class CandidateQualityRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: UUID
    total_score: float
    field_scores: dict[str, int]
    missing_fields: list[str]
    warnings: list[str]


class DuplicateCandidateSuggestionRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: UUID
    score: float
    matched_fields: list[str]
    reasons: list[str]


class DiscoverCandidatesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    only_unassigned: bool = True
    max_results: int = Field(default=200, ge=1, le=500)
    include_domains: list[str] = Field(default_factory=list)
    exclude_domains: list[str] = Field(default_factory=list)
    minimum_eligibility_confidence: float = Field(default=0.7, ge=0, le=1)
    dry_run: bool = False
    include_decisions: bool = True

    @field_validator("include_domains", "exclude_domains", mode="before")
    @classmethod
    def normalize_domains(cls, value: object) -> object:
        if not isinstance(value, list):
            return value
        return sorted(
            {item.strip().casefold() for item in value if isinstance(item, str) and item.strip()}
        )

    @model_validator(mode="after")
    def validate_domains(self) -> Self:
        overlap = set(self.include_domains) & set(self.exclude_domains)
        if overlap:
            raise ValueError("A domain cannot be both included and excluded.")
        return self


class CandidateDiscoveryDecisionRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: CandidateDiscoveryAction
    candidate_id: UUID | None
    search_result_id: UUID
    reason: str
    confidence: float
    matched_by: CandidateMatchedBy
    was_already_linked: bool = False


class CandidateDiscoveryRead(CandidateDiscoveryDecisionRead):
    candidate: CandidateRead | None = None


class CandidateDiscoverySummaryRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: UUID
    dry_run: bool
    received_result_count: int
    candidate_eligible_count: int
    created_candidate_count: int
    linked_existing_count: int
    skipped_count: int
    invalid_count: int
    decisions: list[CandidateDiscoveryDecisionRead]
    warnings: list[str]


class CandidateMergeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_candidate_ids: list[UUID] = Field(min_length=1, max_length=20)
    field_strategy: CandidateFieldStrategy = CandidateFieldStrategy.KEEP_TARGET
    explicit_field_values: dict[str, str | int | bool | None] | None = None
    dry_run: bool = False

    @model_validator(mode="after")
    def validate_source_ids(self) -> Self:
        if len(set(self.source_candidate_ids)) != len(self.source_candidate_ids):
            raise ValueError("Duplicate source candidate IDs are not allowed.")
        return self


class CandidateMergeRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_candidate_id: UUID
    source_candidate_ids: list[UUID]
    field_strategy: CandidateFieldStrategy
    dry_run: bool
    merged_fields: dict[str, object]
    conflicts: list[str]
    warnings: list[str]
    moved_counts: dict[str, int]
    candidate: CandidateRead | None = None
