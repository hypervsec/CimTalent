from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID

from app.db.enums import CandidateProfileStatus, CandidateSource
from app.domain.jobs.types import SortDirection

if TYPE_CHECKING:
    from app.db.models import Candidate


class CandidateDiscoveryAction(StrEnum):
    CREATED = "created"
    LINKED_EXISTING = "linked_existing"
    SKIPPED = "skipped"
    INVALID = "invalid"
    WOULD_CREATE = "would_create"
    WOULD_LINK = "would_link"
    WOULD_SKIP = "would_skip"


class CandidateMatchedBy(StrEnum):
    NORMALIZED_PROFILE_URL = "normalized_profile_url"
    PROFILE_SLUG = "profile_slug"
    MANUAL = "manual"
    NONE = "none"


class CandidateEligibilitySource(StrEnum):
    LINKEDIN_PROFILE = "linkedin_profile"
    GITHUB_PROFILE = "github_profile"
    PERSONAL_PROFILE = "personal_profile"
    UNSUPPORTED = "unsupported"


class CandidateFieldStrategy(StrEnum):
    KEEP_TARGET = "keep_target"
    PREFER_NON_EMPTY = "prefer_non_empty"
    PREFER_NEWEST = "prefer_newest"


class CandidateSortField(StrEnum):
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"
    FULL_NAME = "full_name"
    DATA_QUALITY_SCORE = "data_quality_score"
    TOTAL_EXPERIENCE_MONTHS = "total_experience_months"
    CURRENT_TITLE = "current_title"
    CURRENT_COMPANY = "current_company"


@dataclass(frozen=True, slots=True)
class CandidateDiscoveryInput:
    search_result_id: UUID
    normalized_url: str
    source_url: str
    source_domain: str | None = None
    displayed_name: str | None = None
    displayed_headline: str | None = None
    displayed_location: str | None = None
    title: str | None = None
    snippet: str | None = None
    candidate_profile_slug: str | None = None


@dataclass(frozen=True, slots=True)
class CandidateEligibilityResult:
    eligible: bool
    source_type: CandidateEligibilitySource
    confidence: float
    reason: str


@dataclass(frozen=True, slots=True)
class CandidateDiscoveryDecision:
    action: CandidateDiscoveryAction
    candidate_id: UUID | None
    search_result_id: UUID
    reason: str
    confidence: float
    matched_by: CandidateMatchedBy
    was_already_linked: bool = False


@dataclass(frozen=True, slots=True)
class CandidateDiscoverySummary:
    job_id: UUID
    received_result_count: int
    candidate_eligible_count: int
    created_candidate_count: int
    linked_existing_count: int
    skipped_count: int
    invalid_count: int
    decisions: list[CandidateDiscoveryDecision] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class CandidateWithCounts:
    candidate: Candidate
    experience_count: int = 0
    education_count: int = 0
    skill_count: int = 0
    certification_count: int = 0
    language_count: int = 0
    search_result_count: int = 0
    match_count: int = 0
    shortlist_count: int = 0


@dataclass(frozen=True, slots=True)
class CandidateMergePlan:
    target_candidate_id: UUID
    source_candidate_ids: list[UUID]
    preferred_fields: dict[str, object]
    search_result_ids_to_move: list[UUID]
    conflicts: list[str]
    warnings: list[str]


@dataclass(frozen=True, slots=True)
class DuplicateCandidateSuggestion:
    candidate_id: UUID
    score: float
    matched_fields: list[str]
    reasons: list[str]


@dataclass(frozen=True, slots=True)
class CandidateListFilters:
    source: CandidateSource | None = None
    profile_status: CandidateProfileStatus | None = None
    city: str | None = None
    country: str | None = None
    current_title: str | None = None
    current_company: str | None = None
    min_data_quality: float | None = None
    max_data_quality: float | None = None
    min_experience_months: int | None = None
    max_experience_months: int | None = None
    has_profile_url: bool | None = None
    has_search_results: bool | None = None
    skill: str | None = None
    education_field: str | None = None
    search: str | None = None
    created_from: datetime | None = None
    created_to: datetime | None = None


@dataclass(frozen=True, slots=True)
class CandidateSort:
    field: CandidateSortField = CandidateSortField.CREATED_AT
    direction: SortDirection = SortDirection.DESC


@dataclass(frozen=True, slots=True)
class PagedCandidates:
    items: list[CandidateWithCounts]
    page: int
    page_size: int
    total_items: int

    @property
    def total_pages(self) -> int:
        return (self.total_items + self.page_size - 1) // self.page_size if self.total_items else 0

    @property
    def has_next(self) -> bool:
        return self.page < self.total_pages

    @property
    def has_previous(self) -> bool:
        return self.page > 1 and self.total_pages > 0
