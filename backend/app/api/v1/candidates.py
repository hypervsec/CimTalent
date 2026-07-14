from datetime import datetime
from time import perf_counter
from typing import Annotated, Any
from uuid import UUID

import structlog
from fastapi import APIRouter, Path, Query, Request, Response, status

from app.db.enums import CandidateProfileStatus, CandidateSource
from app.dependencies import (
    CandidateDiscoveryServiceDependency,
    CandidateServiceDependency,
    SessionDependency,
)
from app.domain.candidates import (
    CandidateListFilters,
    CandidateSort,
    CandidateSortField,
    CandidateWithCounts,
)
from app.domain.jobs import SortDirection
from app.schemas.candidates import (
    CandidateCreate,
    CandidateDiscoveryDecisionRead,
    CandidateDiscoveryRead,
    CandidateDiscoverySummaryRead,
    CandidateListItem,
    CandidateMergeRead,
    CandidateMergeRequest,
    CandidateQualityRead,
    CandidateRead,
    CandidateSearchResultRead,
    CandidateUpdate,
    DiscoverCandidatesRequest,
    DuplicateCandidateSuggestionRead,
)
from app.schemas.common import ErrorResponse, PaginatedResponse

router = APIRouter(prefix="/candidates")
result_discovery_router = APIRouter(prefix="/search-results")
job_discovery_router = APIRouter(prefix="/jobs")
logger = structlog.get_logger(__name__)

ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    404: {"model": ErrorResponse, "description": "Candidate was not found."},
    409: {"model": ErrorResponse, "description": "Candidate operation conflicts with state."},
    422: {"description": "Request or candidate validation failed."},
    500: {"model": ErrorResponse, "description": "Internal persistence error."},
}


def candidate_read(record: CandidateWithCounts) -> CandidateRead:
    values = {
        "experience_count": record.experience_count,
        "education_count": record.education_count,
        "skill_count": record.skill_count,
        "certification_count": record.certification_count,
        "language_count": record.language_count,
        "search_result_count": record.search_result_count,
        "match_count": record.match_count,
        "shortlist_count": record.shortlist_count,
    }
    return CandidateRead.model_validate(record.candidate).model_copy(update=values)


def candidate_list_item(record: CandidateWithCounts) -> CandidateListItem:
    return CandidateListItem.model_validate(record.candidate).model_copy(
        update={"search_result_count": record.search_result_count}
    )


def log_event(
    request: Request,
    event: str,
    started_at: float,
    status_code: int,
    candidate_id: UUID | None = None,
) -> None:
    logger.info(
        event,
        request_id=request.state.request_id,
        candidate_id=str(candidate_id) if candidate_id else None,
        duration_ms=round((perf_counter() - started_at) * 1000, 2),
        status_code=status_code,
    )


@router.post(
    "",
    response_model=CandidateRead,
    status_code=status.HTTP_201_CREATED,
    responses=ERROR_RESPONSES,
)
async def create_candidate(
    payload: CandidateCreate,
    request: Request,
    session: SessionDependency,
    service: CandidateServiceDependency,
) -> CandidateRead:
    started_at = perf_counter()
    record = await service.create_candidate(session, data=payload.model_dump(mode="python"))
    log_event(
        request, "candidate_created", started_at, status.HTTP_201_CREATED, record.candidate.id
    )
    return candidate_read(record)


@router.get("", response_model=PaginatedResponse[CandidateListItem], responses=ERROR_RESPONSES)
async def list_candidates(
    request: Request,
    session: SessionDependency,
    service: CandidateServiceDependency,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    source: CandidateSource | None = None,
    profile_status: Annotated[CandidateProfileStatus | None, Query(alias="status")] = None,
    city: str | None = None,
    country: str | None = None,
    current_title: str | None = None,
    current_company: str | None = None,
    min_data_quality: Annotated[float | None, Query(ge=0, le=100)] = None,
    max_data_quality: Annotated[float | None, Query(ge=0, le=100)] = None,
    min_experience_months: Annotated[int | None, Query(ge=0)] = None,
    max_experience_months: Annotated[int | None, Query(ge=0)] = None,
    has_profile_url: bool | None = None,
    has_search_results: bool | None = None,
    skill: str | None = None,
    education_field: str | None = None,
    search: str | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    sort_by: CandidateSortField = CandidateSortField.CREATED_AT,
    sort_direction: SortDirection = SortDirection.DESC,
) -> PaginatedResponse[CandidateListItem]:
    started_at = perf_counter()
    page_data = await service.list_candidates(
        session,
        page=page,
        page_size=page_size,
        filters=CandidateListFilters(
            source=source,
            profile_status=profile_status,
            city=city,
            country=country,
            current_title=current_title,
            current_company=current_company,
            min_data_quality=min_data_quality,
            max_data_quality=max_data_quality,
            min_experience_months=min_experience_months,
            max_experience_months=max_experience_months,
            has_profile_url=has_profile_url,
            has_search_results=has_search_results,
            skill=skill,
            education_field=education_field,
            search=search,
            created_from=created_from,
            created_to=created_to,
        ),
        sort=CandidateSort(sort_by, sort_direction),
    )
    response = PaginatedResponse[CandidateListItem](
        items=[candidate_list_item(item) for item in page_data.items],
        page=page,
        page_size=page_size,
        total_items=page_data.total_items,
        total_pages=page_data.total_pages,
        has_next=page_data.has_next,
        has_previous=page_data.has_previous,
    )
    log_event(request, "candidates_listed", started_at, status.HTTP_200_OK)
    return response


@router.get("/{candidate_id}", response_model=CandidateRead, responses=ERROR_RESPONSES)
async def get_candidate(
    candidate_id: Annotated[UUID, Path()],
    request: Request,
    session: SessionDependency,
    service: CandidateServiceDependency,
) -> CandidateRead:
    started_at = perf_counter()
    record = await service.get_candidate(session, candidate_id)
    log_event(request, "candidate_retrieved", started_at, status.HTTP_200_OK, candidate_id)
    return candidate_read(record)


@router.patch("/{candidate_id}", response_model=CandidateRead, responses=ERROR_RESPONSES)
async def update_candidate(
    candidate_id: Annotated[UUID, Path()],
    payload: CandidateUpdate,
    request: Request,
    session: SessionDependency,
    service: CandidateServiceDependency,
) -> CandidateRead:
    started_at = perf_counter()
    record = await service.update_candidate(
        session,
        candidate_id,
        changes=payload.model_dump(mode="python", exclude_unset=True),
    )
    log_event(request, "candidate_updated", started_at, status.HTTP_200_OK, candidate_id)
    return candidate_read(record)


@router.delete(
    "/{candidate_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    responses=ERROR_RESPONSES,
)
async def delete_candidate(
    candidate_id: Annotated[UUID, Path()],
    request: Request,
    session: SessionDependency,
    service: CandidateServiceDependency,
) -> Response:
    started_at = perf_counter()
    await service.delete_candidate(session, candidate_id)
    log_event(request, "candidate_deleted", started_at, status.HTTP_204_NO_CONTENT, candidate_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{candidate_id}/search-results",
    response_model=list[CandidateSearchResultRead],
    responses=ERROR_RESPONSES,
)
async def list_candidate_search_results(
    candidate_id: Annotated[UUID, Path()],
    session: SessionDependency,
    service: CandidateServiceDependency,
) -> list[CandidateSearchResultRead]:
    results = await service.list_candidate_search_results(session, candidate_id)
    return [
        CandidateSearchResultRead(
            id=result.id,
            source_url=result.source_url,
            normalized_url=result.normalized_url,
            source_domain=result.source_domain,
            title=result.title,
            snippet=result.snippet,
            displayed_name=result.displayed_name,
            displayed_headline=result.displayed_headline,
            displayed_location=result.displayed_location,
            discovered_at=result.discovered_at,
            query_id=result.search_query.id,
            query_text=result.search_query.query_text,
            query_language=result.search_query.language,
            job_id=result.search_query.job_id,
            job_title=result.search_query.job.title,
        )
        for result in results
    ]


@router.get(
    "/{candidate_id}/quality", response_model=CandidateQualityRead, responses=ERROR_RESPONSES
)
async def get_candidate_quality(
    candidate_id: Annotated[UUID, Path()],
    session: SessionDependency,
    service: CandidateServiceDependency,
) -> CandidateQualityRead:
    quality = await service.get_candidate_quality(session, candidate_id)
    return CandidateQualityRead(
        candidate_id=candidate_id,
        total_score=quality.total_score,
        field_scores=quality.field_scores,
        missing_fields=quality.missing_fields,
        warnings=quality.warnings,
    )


@router.get(
    "/{candidate_id}/duplicate-suggestions",
    response_model=list[DuplicateCandidateSuggestionRead],
    responses=ERROR_RESPONSES,
)
async def duplicate_suggestions(
    candidate_id: Annotated[UUID, Path()],
    session: SessionDependency,
    service: CandidateServiceDependency,
    min_score: Annotated[float, Query(ge=0, le=1)] = 0.8,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[DuplicateCandidateSuggestionRead]:
    suggestions = await service.find_duplicate_suggestions(
        session, candidate_id, min_score=min_score, limit=limit
    )
    return [
        DuplicateCandidateSuggestionRead.model_validate(item, from_attributes=True)
        for item in suggestions
    ]


@router.post(
    "/{target_candidate_id}/merge",
    response_model=CandidateMergeRead,
    responses=ERROR_RESPONSES,
)
async def merge_candidates(
    target_candidate_id: Annotated[UUID, Path()],
    payload: CandidateMergeRequest,
    request: Request,
    session: SessionDependency,
    service: CandidateServiceDependency,
) -> CandidateMergeRead:
    started_at = perf_counter()
    logger.info(
        "candidate_merge_started",
        request_id=request.state.request_id,
        target_candidate_id=str(target_candidate_id),
        source_candidate_ids_count=len(payload.source_candidate_ids),
    )
    outcome = await service.merge_candidates(
        session,
        target_candidate_id,
        source_candidate_ids=payload.source_candidate_ids,
        field_strategy=payload.field_strategy,
        explicit_field_values=payload.explicit_field_values,
        dry_run=payload.dry_run,
    )
    logger.info(
        "candidate_merge_completed",
        request_id=request.state.request_id,
        target_candidate_id=str(target_candidate_id),
        source_candidate_ids_count=len(payload.source_candidate_ids),
        action="dry_run" if payload.dry_run else "execute",
        data_quality_score=(
            outcome.candidate.candidate.data_quality_score if outcome.candidate else None
        ),
        duration_ms=round((perf_counter() - started_at) * 1000, 2),
        status_code=status.HTTP_200_OK,
    )
    return CandidateMergeRead(
        target_candidate_id=outcome.target_candidate_id,
        source_candidate_ids=outcome.source_candidate_ids,
        field_strategy=outcome.field_strategy,
        dry_run=outcome.dry_run,
        merged_fields=outcome.merged_fields,
        conflicts=outcome.conflicts,
        warnings=outcome.warnings,
        moved_counts=outcome.moved_counts,
        candidate=candidate_read(outcome.candidate) if outcome.candidate else None,
    )


@result_discovery_router.post(
    "/{result_id}/discover-candidate",
    response_model=CandidateDiscoveryRead,
    responses=ERROR_RESPONSES,
)
async def discover_candidate_from_result(
    result_id: Annotated[UUID, Path()],
    request: Request,
    session: SessionDependency,
    service: CandidateDiscoveryServiceDependency,
) -> CandidateDiscoveryRead:
    started_at = perf_counter()
    outcome = await service.discover_from_result(session, result_id)
    decision = outcome.decision
    logger.info(
        "candidate_discovered",
        request_id=request.state.request_id,
        candidate_id=str(decision.candidate_id) if decision.candidate_id else None,
        search_result_id=str(result_id),
        action=decision.action.value,
        confidence=decision.confidence,
        duration_ms=round((perf_counter() - started_at) * 1000, 2),
        status_code=status.HTTP_200_OK,
    )
    return CandidateDiscoveryRead(
        action=decision.action,
        candidate_id=decision.candidate_id,
        search_result_id=decision.search_result_id,
        reason=decision.reason,
        confidence=decision.confidence,
        matched_by=decision.matched_by,
        was_already_linked=decision.was_already_linked,
        candidate=candidate_read(outcome.candidate) if outcome.candidate else None,
    )


@job_discovery_router.post(
    "/{job_id}/candidates/discover",
    response_model=CandidateDiscoverySummaryRead,
    responses=ERROR_RESPONSES,
)
async def discover_candidates_for_job(
    job_id: Annotated[UUID, Path()],
    payload: DiscoverCandidatesRequest,
    request: Request,
    session: SessionDependency,
    service: CandidateDiscoveryServiceDependency,
) -> CandidateDiscoverySummaryRead:
    started_at = perf_counter()
    summary = await service.discover_for_job(session, job_id, payload)
    decisions = (
        [
            CandidateDiscoveryDecisionRead.model_validate(item, from_attributes=True)
            for item in summary.decisions
        ]
        if payload.include_decisions
        else []
    )
    logger.info(
        "candidate_bulk_discovery_completed",
        request_id=request.state.request_id,
        job_id=str(job_id),
        action="dry_run" if payload.dry_run else "execute",
        created_candidate_count=summary.created_candidate_count,
        linked_existing_count=summary.linked_existing_count,
        duration_ms=round((perf_counter() - started_at) * 1000, 2),
        status_code=status.HTTP_200_OK,
    )
    return CandidateDiscoverySummaryRead(
        job_id=summary.job_id,
        dry_run=payload.dry_run,
        received_result_count=summary.received_result_count,
        candidate_eligible_count=summary.candidate_eligible_count,
        created_candidate_count=summary.created_candidate_count,
        linked_existing_count=summary.linked_existing_count,
        skipped_count=summary.skipped_count,
        invalid_count=summary.invalid_count,
        decisions=decisions,
        warnings=summary.warnings,
    )
