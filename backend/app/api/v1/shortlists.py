# mypy: disable-error-code="no-untyped-def"
from uuid import UUID

from fastapi import APIRouter, Query, Response

from app.db.enums import CandidateSource, ShortlistStatus
from app.dependencies import SessionDependency, ShortlistServiceDependency
from app.schemas.common import PaginatedResponse
from app.schemas.shortlists import MatchSummary, ShortlistCreate, ShortlistRead, ShortlistUpdate

router = APIRouter()


async def _read(entry, service, session) -> ShortlistRead:
    match = await service.repository.match_for(session, entry.job_id, entry.candidate_id)
    summary = (
        MatchSummary(
            match_id=match.id,
            total_score=match.total_score,
            title_score=match.title_score,
            skill_score=match.skill_score,
            experience_score=match.experience_score,
            education_score=match.education_score,
            location_score=match.location_score,
        )
        if match
        else None
    )
    return ShortlistRead.model_validate(entry).model_copy(
        update={"candidate": entry.candidate, "match": summary}
    )


@router.post("/jobs/{job_id}/shortlist/{candidate_id}", response_model=ShortlistRead)
async def add(
    job_id: UUID,
    candidate_id: UUID,
    payload: ShortlistCreate,
    session: SessionDependency,
    service: ShortlistServiceDependency,
):
    return await _read(
        await service.add_or_update_shortlist(
            session, job_id, candidate_id, payload.status, payload.recruiter_note
        ),
        service,
        session,
    )


@router.get("/jobs/{job_id}/shortlist", response_model=PaginatedResponse[ShortlistRead])
async def list_entries(
    job_id: UUID,
    session: SessionDependency,
    service: ShortlistServiceDependency,
    status: ShortlistStatus | None = None,
    min_match_score: float | None = Query(None, ge=0, le=100),
    city: str | None = None,
    source: CandidateSource | None = None,
    search: str | None = None,
    sort_by: str = "created_at",
    sort_direction: str = "desc",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    entries, total = await service.list_job_shortlist(
        session,
        job_id,
        status=status,
        min_match_score=min_match_score,
        city=city,
        source=source,
        search=search,
        sort_by=sort_by,
        descending=sort_direction == "desc",
        offset=(page - 1) * page_size,
        limit=page_size,
    )
    pages = max(1, (total + page_size - 1) // page_size)
    return PaginatedResponse(
        items=[await _read(item, service, session) for item in entries],
        page=page,
        page_size=page_size,
        total_items=total,
        total_pages=pages,
        has_next=page < pages,
        has_previous=page > 1,
    )


@router.get("/shortlist/{shortlist_id}", response_model=ShortlistRead)
async def get(shortlist_id: UUID, session: SessionDependency, service: ShortlistServiceDependency):
    return await _read(await service.get_shortlist_entry(session, shortlist_id), service, session)


@router.patch("/shortlist/{shortlist_id}", response_model=ShortlistRead)
async def update(
    shortlist_id: UUID,
    payload: ShortlistUpdate,
    session: SessionDependency,
    service: ShortlistServiceDependency,
):
    return await _read(
        await service.update_shortlist_entry(
            session,
            shortlist_id,
            status=payload.status,
            recruiter_note=payload.recruiter_note,
            note_set="recruiter_note" in payload.model_fields_set,
        ),
        service,
        session,
    )


@router.delete("/shortlist/{shortlist_id}", status_code=204)
async def delete(
    shortlist_id: UUID, session: SessionDependency, service: ShortlistServiceDependency
) -> Response:
    await service.delete_shortlist_entry(session, shortlist_id)
    return Response(status_code=204)


@router.get("/jobs/{job_id}/shortlist/export.csv")
async def export(
    job_id: UUID, session: SessionDependency, service: ShortlistServiceDependency
) -> Response:
    return Response(
        await service.export_job_shortlist_csv(session, job_id),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="shortlist-{job_id}.csv"'},
    )
