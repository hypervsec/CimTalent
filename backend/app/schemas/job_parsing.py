from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.db.enums import (
    JobStatus,
    RequirementImportance,
    RequirementSource,
    RequirementType,
)


class ParseJobRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    force: bool = False


class ParsedRequirementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    type: RequirementType
    raw_value: str
    normalized_value: str
    importance: RequirementImportance
    weight: float
    confidence: float
    source: RequirementSource
    evidence_text: str | None


class ParseJobResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: UUID
    status: JobStatus
    parser_version: str
    created_requirement_count: int
    updated_job_fields: tuple[str, ...]
    warnings: tuple[str, ...]
    confidence: float
    requirements: tuple[ParsedRequirementRead, ...]
