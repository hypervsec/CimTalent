from dataclasses import dataclass
from uuid import UUID

from app.db.enums import (
    JobStatus,
    RequirementImportance,
    RequirementSource,
    RequirementType,
)


@dataclass(frozen=True, slots=True)
class ParsedRequirement:
    type: RequirementType
    raw_value: str
    normalized_value: str
    importance: RequirementImportance
    weight: float
    confidence: float
    source: RequirementSource = RequirementSource.RULE
    evidence_text: str | None = None
    evidence_start: int | None = None
    evidence_end: int | None = None

    def __post_init__(self) -> None:
        if not self.raw_value.strip() or not self.normalized_value.strip():
            raise ValueError("Requirement values cannot be empty.")
        if self.weight < 0:
            raise ValueError("Requirement weight cannot be negative.")
        if not 0 <= self.confidence <= 1:
            raise ValueError("Requirement confidence must be between zero and one.")


@dataclass(frozen=True, slots=True)
class ParsedJobData:
    description_clean: str
    title_candidates: tuple[str, ...]
    required_skills: tuple[str, ...]
    preferred_skills: tuple[str, ...]
    education_fields: tuple[str, ...]
    education_levels: tuple[str, ...]
    min_experience_years: float | None
    max_experience_years: float | None
    locations: tuple[str, ...]
    languages: tuple[str, ...]
    certifications: tuple[str, ...]
    industries: tuple[str, ...]
    keywords_tr: tuple[str, ...]
    keywords_en: tuple[str, ...]
    requirements: tuple[ParsedRequirement, ...]
    parser_version: str
    warnings: tuple[str, ...]
    confidence: float


@dataclass(frozen=True, slots=True)
class JobParseInput:
    title: str
    description_raw: str
    location_raw: str | None = None
    city: str | None = None
    country: str | None = None


@dataclass(frozen=True, slots=True)
class TextSection:
    title: str
    normalized_title: str
    body: str
    inferred_importance: RequirementImportance
    start: int
    end: int


@dataclass(frozen=True, slots=True)
class EvidenceUnit:
    text: str
    importance: RequirementImportance
    start: int | None = None
    end: int | None = None


@dataclass(frozen=True, slots=True)
class ParserFragment:
    requirements: tuple[ParsedRequirement, ...] = ()
    values: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ExperienceResult:
    requirements: tuple[ParsedRequirement, ...]
    min_years: float | None
    max_years: float | None
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class JobParseOutcome:
    job_id: UUID
    status: JobStatus
    parsed_data: ParsedJobData
    created_requirement_count: int
    updated_job_fields: tuple[str, ...]


def requirement_weight(importance: RequirementImportance) -> float:
    return {
        RequirementImportance.REQUIRED: 1.0,
        RequirementImportance.PREFERRED: 0.6,
        RequirementImportance.OPTIONAL: 0.3,
    }[importance]
