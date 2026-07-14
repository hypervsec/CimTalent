from typing import Self
from uuid import UUID

from pydantic import (
    AnyHttpUrl,
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    field_validator,
    model_validator,
)

from app.db.enums import (
    JobSource,
    JobStatus,
    RequirementImportance,
    RequirementSource,
    RequirementType,
)
from app.schemas.common import UtcDateTime

HTTP_URL_ADAPTER = TypeAdapter(AnyHttpUrl)
LIST_FIELDS = (
    "education_requirements",
    "required_skills",
    "preferred_skills",
    "languages",
    "certifications",
    "keywords_tr",
    "keywords_en",
)
REQUIRED_TEXT_FIELDS = ("company_name", "title", "description_raw")


def normalize_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        raise ValueError("Value must be a list of non-empty strings.")
    normalized: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ValueError("List items must be non-empty strings.")
        clean = item.strip()
        key = clean.casefold()
        if key not in seen:
            seen.add(key)
            normalized.append(clean)
    return normalized


def validate_url(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("URL must be a string.")
    clean = value.strip()
    if not clean:
        return None
    return str(HTTP_URL_ADAPTER.validate_python(clean))


class JobCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: JobSource = JobSource.MANUAL
    source_url: str | None = Field(default=None, max_length=2048)
    company_name: str = Field(min_length=1, max_length=255)
    title: str = Field(min_length=1, max_length=255)
    description_raw: str = Field(min_length=1)
    location_raw: str | None = Field(default=None, max_length=500)
    city: str | None = Field(default=None, max_length=120)
    country: str | None = Field(default=None, max_length=120)
    employment_type: str | None = Field(default=None, max_length=120)
    seniority_level: str | None = Field(default=None, max_length=120)
    min_experience_years: float | None = Field(default=None, ge=0)
    max_experience_years: float | None = Field(default=None, ge=0)
    education_requirements: list[str] = Field(default_factory=list)
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    keywords_tr: list[str] = Field(default_factory=list)
    keywords_en: list[str] = Field(default_factory=list)

    @field_validator(*REQUIRED_TEXT_FIELDS, mode="before")
    @classmethod
    def trim_required_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("source_url", mode="before")
    @classmethod
    def validate_source_url(cls, value: object) -> str | None:
        return validate_url(value)

    @field_validator(*LIST_FIELDS, mode="before")
    @classmethod
    def validate_string_lists(cls, value: object) -> list[str]:
        return normalize_string_list(value)

    @model_validator(mode="after")
    def validate_cross_fields(self) -> Self:
        if self.source is not JobSource.MANUAL and self.source_url is None:
            raise ValueError("source_url is required for non-manual job sources.")
        if (
            self.min_experience_years is not None
            and self.max_experience_years is not None
            and self.max_experience_years < self.min_experience_years
        ):
            raise ValueError("max_experience_years cannot be lower than min_experience_years.")
        return self


class JobUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: JobSource | None = None
    source_url: str | None = Field(default=None, max_length=2048)
    company_name: str | None = Field(default=None, min_length=1, max_length=255)
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description_raw: str | None = Field(default=None, min_length=1)
    description_clean: str | None = None
    location_raw: str | None = Field(default=None, max_length=500)
    city: str | None = Field(default=None, max_length=120)
    country: str | None = Field(default=None, max_length=120)
    employment_type: str | None = Field(default=None, max_length=120)
    seniority_level: str | None = Field(default=None, max_length=120)
    min_experience_years: float | None = Field(default=None, ge=0)
    max_experience_years: float | None = Field(default=None, ge=0)
    education_requirements: list[str] | None = None
    required_skills: list[str] | None = None
    preferred_skills: list[str] | None = None
    languages: list[str] | None = None
    certifications: list[str] | None = None
    keywords_tr: list[str] | None = None
    keywords_en: list[str] | None = None
    status: JobStatus | None = None

    @field_validator(*REQUIRED_TEXT_FIELDS, mode="before")
    @classmethod
    def trim_required_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("source_url", mode="before")
    @classmethod
    def validate_source_url(cls, value: object) -> str | None:
        return validate_url(value)

    @field_validator(*LIST_FIELDS, mode="before")
    @classmethod
    def validate_string_lists(cls, value: object) -> list[str] | None:
        if value is None:
            return None
        return normalize_string_list(value)

    @model_validator(mode="after")
    def validate_partial_fields(self) -> Self:
        non_nullable = (*REQUIRED_TEXT_FIELDS, *LIST_FIELDS, "source", "status")
        for field_name in non_nullable:
            if field_name in self.model_fields_set and getattr(self, field_name) is None:
                raise ValueError(f"{field_name} cannot be null.")
        if (
            self.min_experience_years is not None
            and self.max_experience_years is not None
            and self.max_experience_years < self.min_experience_years
        ):
            raise ValueError("max_experience_years cannot be lower than min_experience_years.")
        if (
            "source" in self.model_fields_set
            and self.source is not None
            and self.source is not JobSource.MANUAL
            and "source_url" in self.model_fields_set
            and self.source_url is None
        ):
            raise ValueError("source_url is required for non-manual job sources.")
        return self


class JobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    source: JobSource
    source_url: str | None
    company_name: str
    title: str
    description_raw: str
    description_clean: str | None
    location_raw: str | None
    city: str | None
    country: str | None
    employment_type: str | None
    seniority_level: str | None
    min_experience_years: float | None
    max_experience_years: float | None
    education_requirements: list[str]
    required_skills: list[str]
    preferred_skills: list[str]
    languages: list[str]
    certifications: list[str]
    keywords_tr: list[str]
    keywords_en: list[str]
    status: JobStatus
    created_at: UtcDateTime
    updated_at: UtcDateTime
    requirement_count: int = 0
    search_query_count: int = 0
    candidate_match_count: int = 0
    shortlist_count: int = 0


class JobListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    source: JobSource
    company_name: str
    title: str
    city: str | None
    country: str | None
    status: JobStatus
    min_experience_years: float | None
    max_experience_years: float | None
    created_at: UtcDateTime
    updated_at: UtcDateTime
    requirement_count: int = 0
    search_query_count: int = 0
    candidate_match_count: int = 0
    shortlist_count: int = 0


class JobRequirementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    job_id: UUID
    type: RequirementType
    raw_value: str
    normalized_value: str
    importance: RequirementImportance
    weight: float
    confidence: float
    source: RequirementSource
    created_at: UtcDateTime
    updated_at: UtcDateTime
