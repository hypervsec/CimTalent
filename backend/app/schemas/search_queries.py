from urllib.parse import urlencode
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

from app.db.enums import SearchLanguage, SearchSource, SearchStatus
from app.domain.sourcing.exceptions import InvalidTargetDomainError
from app.domain.sourcing.normalizers import normalize_target_domain
from app.domain.sourcing.types import QueryType
from app.schemas.common import UtcDateTime


class GenerateQueriesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_queries: int = Field(default=10, ge=1, le=30)
    languages: list[SearchLanguage] = Field(
        default_factory=lambda: [SearchLanguage.TR, SearchLanguage.EN]
    )
    target_domain: str = "linkedin.com/in"

    @field_validator("languages")
    @classmethod
    def validate_languages(cls, value: list[SearchLanguage]) -> list[SearchLanguage]:
        result = list(dict.fromkeys(value))
        if not result:
            raise ValueError("At least one language is required.")
        return result

    @field_validator("target_domain")
    @classmethod
    def validate_target_domain(cls, value: str) -> str:
        try:
            return normalize_target_domain(value)
        except InvalidTargetDomainError as exc:
            raise ValueError(exc.message) from exc


class GeneratedQueryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    job_id: UUID
    source: SearchSource
    language: SearchLanguage
    query_text: str
    normalized_query_key: str
    query_type: QueryType
    precision_level: int
    expected_intent: str
    included_titles: list[str]
    included_skills: list[str]
    included_locations: list[str]
    status: SearchStatus
    result_count: int
    created_at: UtcDateTime
    executed_at: UtcDateTime | None

    @computed_field
    def google_search_url(self) -> str:
        return f"https://www.google.com/search?{urlencode({'q': self.query_text})}"


class GenerateQueriesResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: UUID
    generated_count: int
    created_count: int
    existing_count: int
    skipped_count: int
    queries: list[GeneratedQueryRead]
