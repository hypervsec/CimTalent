from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.db.enums import ShortlistStatus
from app.schemas.candidates import CandidateRead
from app.schemas.common import UtcDateTime


class ShortlistCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: ShortlistStatus = ShortlistStatus.SHORTLISTED
    recruiter_note: str | None = Field(default=None, max_length=10_000)


class ShortlistUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: ShortlistStatus | None = None
    recruiter_note: str | None = Field(default=None, max_length=10_000)


class MatchSummary(BaseModel):
    match_id: UUID
    total_score: float
    title_score: float
    skill_score: float
    experience_score: float
    education_score: float
    location_score: float


class ShortlistRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    job_id: UUID
    candidate_id: UUID
    status: ShortlistStatus
    recruiter_note: str | None
    candidate: CandidateRead
    match: MatchSummary | None = None
    created_at: UtcDateTime
    updated_at: UtcDateTime
