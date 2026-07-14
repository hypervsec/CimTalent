# mypy: disable-error-code="no-untyped-def"
from uuid import UUID

from fastapi import APIRouter, Query

from app.db.enums import CandidateProfileStatus, CandidateSource
from app.dependencies import CandidateMatchingServiceDependency, SessionDependency
from app.schemas.common import PaginatedResponse
from app.schemas.matching import CandidateMatchRead, MatchCalculateRequest

router = APIRouter()


def _read(record) -> CandidateMatchRead:
    candidate = record.candidate
    return CandidateMatchRead.model_validate(record).model_copy(
        update={
            "candidate_name": candidate.full_name if candidate else None,
            "candidate_title": candidate.current_title if candidate else None,
            "candidate_city": candidate.city if candidate else None,
            "candidate_source": candidate.source if candidate else None,
        }
    )


@router.post("/jobs/{job_id}/matches/calculate", response_model=list[CandidateMatchRead])
async def calculate_all(
    job_id: UUID,
    payload: MatchCalculateRequest,
    session: SessionDependency,
    service: CandidateMatchingServiceDependency,
):
    return [
        _read(item)
        for item in await service.calculate_all_matches(session, job_id, payload.candidate_ids)
    ]


@router.post("/jobs/{job_id}/candidates/{candidate_id}/match", response_model=CandidateMatchRead)
async def calculate_one(
    job_id: UUID,
    candidate_id: UUID,
    session: SessionDependency,
    service: CandidateMatchingServiceDependency,
):
    return _read(await service.calculate_match(session, job_id, candidate_id))


@router.get("/jobs/{job_id}/matches", response_model=PaginatedResponse[CandidateMatchRead])
async def list_matches(
    job_id: UUID,
    session: SessionDependency,
    service: CandidateMatchingServiceDependency,
    min_score: float | None = Query(None, ge=0, le=100),
    max_score: float | None = Query(None, ge=0, le=100),
    city: str | None = None,
    source: CandidateSource | None = None,
    profile_status: CandidateProfileStatus | None = None,
    sort_by: str = "total_score",
    sort_direction: str = "desc",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    records, total = await service.list_job_matches(
        session,
        job_id,
        min_score=min_score,
        max_score=max_score,
        city=city,
        source=source,
        profile_status=profile_status,
        sort_by=sort_by,
        descending=sort_direction == "desc",
        offset=(page - 1) * page_size,
        limit=page_size,
    )
    pages = max(1, (total + page_size - 1) // page_size)
    return PaginatedResponse(
        items=[_read(item) for item in records],
        page=page,
        page_size=page_size,
        total_items=total,
        total_pages=pages,
        has_next=page < pages,
        has_previous=page > 1,
    )


@router.get("/matches/{match_id}", response_model=CandidateMatchRead)
async def get_match(
    match_id: UUID, session: SessionDependency, service: CandidateMatchingServiceDependency
):
    return _read(await service.get_match(session, match_id))


@router.post("/matches/{match_id}/recalculate", response_model=CandidateMatchRead)
async def recalculate(
    match_id: UUID, session: SessionDependency, service: CandidateMatchingServiceDependency
):
    return _read(await service.recalculate_match(session, match_id))
