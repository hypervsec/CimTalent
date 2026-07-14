from __future__ import annotations

from datetime import date
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.db.enums import CandidateProfileStatus, CandidateSkillSource
from app.domain.enrichment.enums import (
    CandidateEnrichmentStatus,
    EnrichmentImportMode,
    EnrichmentMode,
    EnrichmentProvider,
    IdentityUpdateStrategy,
)
from app.schemas.candidates import CandidateQualityRead, CandidateRead
from app.schemas.common import UtcDateTime


class ExtractedTextInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: str = Field(min_length=1, max_length=20_000)
    source: str = Field(default="manual", min_length=1, max_length=120)
    confidence: float = Field(default=1.0, ge=0, le=1)
    evidence: str | None = Field(default=None, max_length=2_000)

    @field_validator("value", "source", "evidence", mode="before")
    @classmethod
    def trim(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class ExtractedBooleanInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: bool
    source: str = Field(default="manual", min_length=1, max_length=120)
    confidence: float = Field(default=1.0, ge=0, le=1)
    evidence: str | None = Field(default=None, max_length=2_000)


class EnrichedIdentityInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    full_name: ExtractedTextInput | None = None
    headline: ExtractedTextInput | None = None
    about: ExtractedTextInput | None = None
    location_raw: ExtractedTextInput | None = None
    city: ExtractedTextInput | None = None
    country: ExtractedTextInput | None = None
    current_title: ExtractedTextInput | None = None
    current_company: ExtractedTextInput | None = None
    open_to_work: ExtractedBooleanInput | None = None


class ExperienceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    external_key: str | None = Field(default=None, max_length=500)
    position_title_raw: str = Field(min_length=1, max_length=500)
    company_name: str | None = Field(default=None, max_length=255)
    company_url: str | None = Field(default=None, max_length=2048)
    employment_type: str | None = Field(default=None, max_length=120)
    location: str | None = Field(default=None, max_length=500)
    start_date: date | None = None
    end_date: date | None = None
    is_current: bool = False
    duration_months: int | None = Field(default=None, ge=0)
    description: str | None = Field(default=None, max_length=20_000)
    skills_detected: list[str] = Field(default_factory=list, max_length=500)
    industry_detected: str | None = Field(default=None, max_length=255)
    confidence: float = Field(default=1.0, ge=0, le=1)
    source: str = Field(default="manual", min_length=1, max_length=120)
    sort_order: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def dates_are_consistent(self) -> Self:
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date cannot precede start_date")
        if self.is_current and self.end_date:
            raise ValueError("current experience cannot have an end_date")
        return self


class EducationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    external_key: str | None = Field(default=None, max_length=500)
    institution_name: str = Field(min_length=1, max_length=500)
    degree: str | None = Field(default=None, max_length=255)
    field_of_study: str | None = Field(default=None, max_length=255)
    start_year: int | None = Field(default=None, ge=1900, le=2100)
    end_year: int | None = Field(default=None, ge=1900, le=2100)
    grade: str | None = Field(default=None, max_length=120)
    description: str | None = Field(default=None, max_length=20_000)
    confidence: float = Field(default=1.0, ge=0, le=1)
    source: str = Field(default="manual", min_length=1, max_length=120)
    sort_order: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def years_are_consistent(self) -> Self:
        if self.start_year and self.end_year and self.end_year < self.start_year:
            raise ValueError("end_year cannot precede start_year")
        return self


class SkillInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    raw_name: str = Field(min_length=1, max_length=255)
    category: str | None = Field(default=None, max_length=120)
    endorsement_count: int | None = Field(default=None, ge=0)
    source: CandidateSkillSource = CandidateSkillSource.MANUAL
    confidence: float = Field(default=1.0, ge=0, le=1)


class CertificationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    external_key: str | None = Field(default=None, max_length=500)
    name: str = Field(min_length=1, max_length=500)
    issuer: str | None = Field(default=None, max_length=255)
    issue_date: date | None = None
    expiration_date: date | None = None
    credential_id: str | None = Field(default=None, max_length=255)
    credential_url: str | None = Field(default=None, max_length=2048)
    source: str = Field(default="manual", min_length=1, max_length=120)
    confidence: float = Field(default=1.0, ge=0, le=1)

    @model_validator(mode="after")
    def dates_are_consistent(self) -> Self:
        if self.issue_date and self.expiration_date and self.expiration_date < self.issue_date:
            raise ValueError("expiration_date cannot precede issue_date")
        return self


class LanguageInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    language: str = Field(min_length=1, max_length=120)
    proficiency: str | None = Field(default=None, max_length=120)
    confidence: float = Field(default=1.0, ge=0, le=1)
    source: str = Field(default="manual", min_length=1, max_length=120)


class CandidateEnrichmentImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: EnrichmentProvider = EnrichmentProvider.MANUAL
    mode: EnrichmentMode = EnrichmentMode.FAST
    import_mode: EnrichmentImportMode = EnrichmentImportMode.MERGE
    identity_update_strategy: IdentityUpdateStrategy = IdentityUpdateStrategy.FILL_EMPTY
    identity: EnrichedIdentityInput | None = None
    experiences: list[ExperienceInput] = Field(default_factory=list, max_length=200)
    educations: list[EducationInput] = Field(default_factory=list, max_length=50)
    skills: list[SkillInput] = Field(default_factory=list, max_length=500)
    certifications: list[CertificationInput] = Field(default_factory=list, max_length=200)
    languages: list[LanguageInput] = Field(default_factory=list, max_length=50)
    parser_version: str = Field(default="manual-v1", min_length=1, max_length=100)
    warnings: list[str] = Field(default_factory=list, max_length=100)
    is_partial: bool = False


class EnrichmentIdentityChangeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    field: str
    old_value: object
    new_value: object
    action: str
    reason: str
    confidence: float


class EnrichmentCollectionDiffRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    section: str
    create_count: int
    update_count: int
    delete_count: int
    unchanged_count: int
    conflicts: list[str] | tuple[str, ...]
    warnings: list[str] | tuple[str, ...]


class CandidateEnrichmentDiffRead(BaseModel):
    model_config = ConfigDict(extra="forbid")
    identity_changes: list[EnrichmentIdentityChangeRead]
    experiences: EnrichmentCollectionDiffRead
    educations: EnrichmentCollectionDiffRead
    skills: EnrichmentCollectionDiffRead
    certifications: EnrichmentCollectionDiffRead
    languages: EnrichmentCollectionDiffRead
    predicted_quality_before: float
    predicted_quality_after: float
    warnings: list[str]


class CandidateEnrichmentRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: UUID
    candidate_id: UUID
    provider: EnrichmentProvider
    mode: EnrichmentMode
    status: CandidateEnrichmentStatus
    source_url: str | None
    parser_version: str | None
    requested_sections: list[object]
    completed_sections: list[object]
    warning_codes: list[object]
    error_codes: list[object]
    input_summary: dict[str, object]
    result_summary: dict[str, object]
    data_quality_before: float
    data_quality_after: float | None
    created_experience_count: int
    updated_experience_count: int
    deleted_experience_count: int
    created_education_count: int
    updated_education_count: int
    deleted_education_count: int
    created_skill_count: int
    updated_skill_count: int
    deleted_skill_count: int
    created_certification_count: int
    updated_certification_count: int
    deleted_certification_count: int
    created_language_count: int
    updated_language_count: int
    deleted_language_count: int
    started_at: UtcDateTime | None
    completed_at: UtcDateTime | None
    created_at: UtcDateTime
    updated_at: UtcDateTime


class CandidateEnrichmentPreviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    candidate_id: UUID
    mode: EnrichmentMode
    import_mode: EnrichmentImportMode
    identity_update_strategy: IdentityUpdateStrategy
    diff: CandidateEnrichmentDiffRead
    warnings: list[str]


class CandidateEnrichmentImportResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    candidate: CandidateRead
    run: CandidateEnrichmentRunRead
    mode: EnrichmentMode
    import_mode: EnrichmentImportMode
    identity_update_strategy: IdentityUpdateStrategy
    data_quality_before: float
    data_quality_after: float
    profile_status_before: CandidateProfileStatus
    profile_status_after: CandidateProfileStatus
    diff: CandidateEnrichmentDiffRead
    warnings: list[str]


class CandidateExperienceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: UUID
    external_key: str | None
    source: str | None
    position_title_raw: str
    position_title_normalized: str | None
    company_name: str | None
    company_url: str | None
    employment_type: str | None
    location: str | None
    start_date: date | None
    end_date: date | None
    is_current: bool
    duration_months: int | None
    description: str | None
    skills_detected: list[object]
    industry_detected: str | None
    confidence: float
    sort_order: int


class CandidateEducationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: UUID
    external_key: str | None
    source: str | None
    institution_name: str
    degree: str | None
    field_of_study: str | None
    field_of_study_normalized: str | None
    start_year: int | None
    end_year: int | None
    grade: str | None
    description: str | None
    confidence: float
    sort_order: int


class CandidateSkillRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: UUID
    raw_name: str
    normalized_name: str
    category: str | None
    endorsement_count: int | None
    source: CandidateSkillSource
    confidence: float


class CandidateCertificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: UUID
    external_key: str | None
    source: str | None
    name: str
    issuer: str | None
    issue_date: date | None
    expiration_date: date | None
    credential_id: str | None
    credential_url: str | None
    confidence: float


class CandidateLanguageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: UUID
    language: str
    language_normalized: str
    proficiency: str | None
    confidence: float
    source: str | None


class CandidateProfileSnapshotRead(BaseModel):
    model_config = ConfigDict(extra="forbid")
    candidate: CandidateRead
    experiences: list[CandidateExperienceRead]
    educations: list[CandidateEducationRead]
    skills: list[CandidateSkillRead]
    certifications: list[CandidateCertificationRead]
    languages: list[CandidateLanguageRead]
    quality: CandidateQualityRead
    latest_enrichment_run: CandidateEnrichmentRunRead | None


class CandidateEnrichmentRunPage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[CandidateEnrichmentRunRead]
    page: int
    page_size: int
    total_items: int
    total_pages: int
