from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Protocol
from uuid import UUID

from app.db.enums import CandidateSkillSource
from app.domain.enrichment.enums import EnrichmentMode, EnrichmentProvider, EnrichmentSection

JsonValue = str | int | float | bool | None | list["JsonValue"] | dict[str, "JsonValue"]


@dataclass(frozen=True, slots=True)
class ExtractedText:
    value: str
    source: str
    confidence: float = 1.0
    evidence: str | None = None


@dataclass(frozen=True, slots=True)
class ExtractedBoolean:
    value: bool
    source: str
    confidence: float = 1.0
    evidence: str | None = None


@dataclass(frozen=True, slots=True)
class EnrichedCandidateIdentity:
    full_name: ExtractedText | None = None
    headline: ExtractedText | None = None
    about: ExtractedText | None = None
    location_raw: ExtractedText | None = None
    city: ExtractedText | None = None
    country: ExtractedText | None = None
    current_title: ExtractedText | None = None
    current_company: ExtractedText | None = None
    open_to_work: ExtractedBoolean | None = None


@dataclass(frozen=True, slots=True)
class EnrichedExperience:
    position_title_raw: str
    external_key: str | None = None
    position_title_normalized: str | None = None
    company_name: str | None = None
    company_url: str | None = None
    employment_type: str | None = None
    location: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    is_current: bool = False
    duration_months: int | None = None
    description: str | None = None
    skills_detected: tuple[str, ...] = ()
    industry_detected: str | None = None
    confidence: float = 1.0
    source: str = "manual"
    sort_order: int = 0


@dataclass(frozen=True, slots=True)
class EnrichedEducation:
    institution_name: str
    external_key: str | None = None
    degree: str | None = None
    field_of_study: str | None = None
    field_of_study_normalized: str | None = None
    start_year: int | None = None
    end_year: int | None = None
    grade: str | None = None
    description: str | None = None
    confidence: float = 1.0
    source: str = "manual"
    sort_order: int = 0


@dataclass(frozen=True, slots=True)
class EnrichedSkill:
    raw_name: str
    normalized_name: str
    category: str | None = None
    endorsement_count: int | None = None
    source: CandidateSkillSource = CandidateSkillSource.MANUAL
    confidence: float = 1.0


@dataclass(frozen=True, slots=True)
class EnrichedCertification:
    name: str
    external_key: str | None = None
    issuer: str | None = None
    issue_date: date | None = None
    expiration_date: date | None = None
    credential_id: str | None = None
    credential_url: str | None = None
    source: str = "manual"
    confidence: float = 1.0


@dataclass(frozen=True, slots=True)
class EnrichedLanguage:
    language: str
    language_normalized: str
    proficiency: str | None = None
    confidence: float = 1.0
    source: str = "manual"


@dataclass(frozen=True, slots=True)
class EnrichmentItemError:
    section: EnrichmentSection
    code: str
    message: str
    item_index: int | None = None


@dataclass(frozen=True, slots=True)
class CandidateEnrichmentRequest:
    candidate_id: UUID
    profile_url: str | None
    mode: EnrichmentMode
    requested_sections: tuple[EnrichmentSection, ...]
    correlation_id: str | None = None


@dataclass(frozen=True, slots=True)
class CandidateEnrichmentResult:
    provider: EnrichmentProvider
    mode: EnrichmentMode
    started_at: datetime
    completed_at: datetime
    source_url: str | None = None
    identity: EnrichedCandidateIdentity | None = None
    experiences: tuple[EnrichedExperience, ...] = ()
    educations: tuple[EnrichedEducation, ...] = ()
    skills: tuple[EnrichedSkill, ...] = ()
    certifications: tuple[EnrichedCertification, ...] = ()
    languages: tuple[EnrichedLanguage, ...] = ()
    warnings: tuple[str, ...] = ()
    errors: tuple[EnrichmentItemError, ...] = ()
    data_quality_before: float | None = None
    provider_metadata: Mapping[str, JsonValue] = field(default_factory=dict)
    parser_version: str = "manual-v1"
    is_partial: bool = False


class CandidateEnrichmentProvider(Protocol):
    async def enrich(self, request: CandidateEnrichmentRequest) -> CandidateEnrichmentResult: ...
