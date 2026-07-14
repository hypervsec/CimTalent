from dataclasses import dataclass
from enum import IntEnum, StrEnum
from uuid import UUID

from app.db.enums import (
    RequirementImportance,
    RequirementType,
    SearchLanguage,
    SearchSource,
    SearchStatus,
)
from app.domain.jobs.types import SortDirection


class QueryType(StrEnum):
    TITLE_LOCATION = "title_location"
    TITLE_SKILLS = "title_skills"
    EDUCATION_LOCATION = "education_location"
    INDUSTRY_TITLE = "industry_title"
    TITLE_SYNONYMS = "title_synonyms"
    REQUIRED_SKILLS = "required_skills"
    PRECISION = "precision"
    RECALL = "recall"
    BROAD_LOCATION = "broad_location"
    CUSTOM = "custom"


class QueryPrecision(IntEnum):
    BROAD_RECALL = 1
    BROAD = 2
    BALANCED = 3
    PRECISE = 4
    STRICT = 5


class ManualImportFormat(StrEnum):
    JSON = "json"
    URLS = "urls"
    HTML = "html"


class ImportMode(StrEnum):
    MERGE = "merge"
    REPLACE = "replace"


class SearchQuerySortField(StrEnum):
    CREATED_AT = "created_at"
    PRECISION_LEVEL = "precision_level"
    LANGUAGE = "language"
    RESULT_COUNT = "result_count"


@dataclass(frozen=True, slots=True)
class SearchQueryFilters:
    source: SearchSource | None = None
    language: SearchLanguage | None = None
    status: SearchStatus | None = None
    query_type: QueryType | None = None
    precision_level: int | None = None


@dataclass(frozen=True, slots=True)
class SearchQuerySort:
    field: SearchQuerySortField = SearchQuerySortField.CREATED_AT
    direction: SortDirection = SortDirection.DESC


class SearchResultSortField(StrEnum):
    DISCOVERED_AT = "discovered_at"
    RESULT_RANK = "result_rank"
    PRE_SCORE = "pre_score"
    TITLE = "title"


@dataclass(frozen=True, slots=True)
class SearchResultFilters:
    query_id: UUID | None = None
    source_domain: str | None = None
    is_duplicate: bool | None = None
    min_pre_score: float | None = None
    candidate_assigned: bool | None = None
    language: SearchLanguage | None = None
    query_type: QueryType | None = None


@dataclass(frozen=True, slots=True)
class SearchResultSort:
    field: SearchResultSortField = SearchResultSortField.DISCOVERED_AT
    direction: SortDirection = SortDirection.DESC


@dataclass(frozen=True, slots=True)
class QueryRequirementInput:
    type: RequirementType
    normalized_value: str
    raw_value: str
    importance: RequirementImportance
    weight: float
    confidence: float


@dataclass(frozen=True, slots=True)
class QueryGenerationInput:
    job_id: UUID
    job_title: str
    city: str | None
    country: str | None
    required_skills: tuple[str, ...]
    preferred_skills: tuple[str, ...]
    keywords_tr: tuple[str, ...]
    keywords_en: tuple[str, ...]
    requirements: tuple[QueryRequirementInput, ...]
    max_queries: int = 10
    languages: tuple[SearchLanguage, ...] = (SearchLanguage.TR, SearchLanguage.EN)
    target_domain: str = "linkedin.com/in"


@dataclass(frozen=True, slots=True)
class GeneratedQuery:
    source: SearchSource
    language: SearchLanguage
    query_text: str
    query_type: QueryType
    precision_level: int
    expected_intent: str
    included_titles: tuple[str, ...]
    included_skills: tuple[str, ...]
    included_locations: tuple[str, ...]
    normalized_query_key: str


@dataclass(frozen=True, slots=True)
class ParsedManualSearchResult:
    source_url: str
    normalized_url: str
    source_domain: str | None
    title: str | None = None
    snippet: str | None = None
    displayed_name: str | None = None
    displayed_headline: str | None = None
    displayed_location: str | None = None
    result_rank: int | None = None
    candidate_profile_slug: str | None = None


@dataclass(frozen=True, slots=True)
class SearchResultImportSummary:
    received_count: int
    valid_count: int
    inserted_count: int
    duplicate_count: int
    invalid_count: int
    warnings: tuple[str, ...]
    results: tuple[ParsedManualSearchResult, ...]


@dataclass(frozen=True, slots=True)
class ManualResultInputData:
    url: str
    title: str | None = None
    snippet: str | None = None
    displayed_name: str | None = None
    displayed_headline: str | None = None
    displayed_location: str | None = None
    rank: int | None = None


@dataclass(frozen=True, slots=True)
class ManualParseOutcome:
    received_count: int
    duplicate_count: int
    invalid_count: int
    warnings: tuple[str, ...]
    results: tuple[ParsedManualSearchResult, ...]
