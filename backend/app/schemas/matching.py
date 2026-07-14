from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.db.enums import CandidateProfileStatus, CandidateSource
from app.schemas.common import UtcDateTime


class MatchCalculateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    candidate_ids: list[UUID] | None = Field(default=None, max_length=500)
    recalculate_existing: bool = True


class CandidateMatchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    job_id: UUID
    candidate_id: UUID
    candidate_name: str | None = None
    candidate_title: str | None = None
    candidate_city: str | None = None
    candidate_source: CandidateSource | None = None
    total_score: float
    title_score: float
    skill_score: float
    experience_score: float
    industry_score: float
    education_score: float
    location_score: float
    language_score: float
    certification_score: float
    matched_requirements: list[object]
    missing_requirements: list[object]
    uncertain_requirements: list[object]
    explanation: str | None
    score_version: str
    created_at: UtcDateTime
    updated_at: UtcDateTime


class MatchListFilters(BaseModel):
    min_score: float | None = Field(default=None, ge=0, le=100)
    max_score: float | None = Field(default=None, ge=0, le=100)
    city: str | None = None
    source: CandidateSource | None = None
    profile_status: CandidateProfileStatus | None = None
    sort_by: str = "total_score"
    sort_direction: str = "desc"
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
