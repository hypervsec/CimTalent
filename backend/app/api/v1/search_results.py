from math import ceil
from time import perf_counter
from typing import Annotated, Any
from uuid import UUID

import structlog
from fastapi import APIRouter, Path, Query, Request, Response, status

from app.db.enums import SearchLanguage
from app.dependencies import SearchResultImportServiceDependency, SessionDependency
from app.domain.jobs.types import SortDirection
from app.domain.sourcing.types import (
    QueryType,
    SearchResultFilters,
    SearchResultSort,
    SearchResultSortField,
)
from app.schemas.common import ErrorResponse, PaginatedResponse
from app.schemas.search_results import (
    ImportSearchResultsRequest,
    ImportSearchResultsResponse,
    SearchResultRead,
)

query_router = APIRouter(prefix="/queries")
job_router = APIRouter(prefix="/jobs")
result_router = APIRouter(prefix="/search-results")
logger = structlog.get_logger(__name__)
ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    404: {"model": ErrorResponse},
    413: {"model": ErrorResponse},
    422: {"description": "Manual import validation failed."},
    500: {"model": ErrorResponse},
}


def _page_response(result: Any, page: int, page_size: int) -> PaginatedResponse[SearchResultRead]:
    total_pages = ceil(result.total_items / page_size) if result.total_items else 0
    return PaginatedResponse[SearchResultRead](
        items=[SearchResultRead.model_validate(item) for item in result.items],
        page=page,
        page_size=page_size,
        total_items=result.total_items,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_previous=page > 1,
    )


@query_router.post(
    "/{query_id}/import-results",
    response_model=ImportSearchResultsResponse,
    responses=ERROR_RESPONSES,
)
async def import_results(
    query_id: Annotated[UUID, Path()],
    payload: ImportSearchResultsRequest,
    request: Request,
    session: SessionDependency,
    service: SearchResultImportServiceDependency,
) -> ImportSearchResultsResponse:
    started_at = perf_counter()
    logger.info(
        "search_results_import_started",
        request_id=request.state.request_id,
        query_id=str(query_id),
        import_format=payload.format.value,
        import_mode=payload.mode.value,
    )
    outcome = await service.import_results(
        session,
        query_id,
        import_format=payload.format,
        mode=payload.mode,
        payload=payload.domain_payload(),
    )
    logger.info(
        "search_results_import_completed",
        request_id=request.state.request_id,
        query_id=str(query_id),
        imported_count=outcome.inserted_count,
        duplicate_count=outcome.duplicate_count,
        invalid_count=outcome.invalid_count,
        import_format=payload.format.value,
        import_mode=payload.mode.value,
        duration_ms=round((perf_counter() - started_at) * 1000, 2),
        status_code=status.HTTP_200_OK,
    )
    return ImportSearchResultsResponse(
        query_id=outcome.query_id,
        mode=outcome.mode,
        received_count=outcome.received_count,
        valid_count=outcome.valid_count,
        inserted_count=outcome.inserted_count,
        duplicate_count=outcome.duplicate_count,
        invalid_count=outcome.invalid_count,
        total_query_result_count=outcome.total_query_result_count,
        warnings=outcome.warnings,
        results=[SearchResultRead.model_validate(item) for item in outcome.results],
    )


@query_router.get(
    "/{query_id}/results",
    response_model=PaginatedResponse[SearchResultRead],
    responses=ERROR_RESPONSES,
)
async def list_query_results(
    query_id: Annotated[UUID, Path()],
    session: SessionDependency,
    service: SearchResultImportServiceDependency,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    source_domain: str | None = None,
    is_duplicate: bool | None = None,
    min_pre_score: Annotated[float | None, Query(ge=0, le=100)] = None,
    sort_by: SearchResultSortField = SearchResultSortField.DISCOVERED_AT,
    sort_direction: SortDirection = SortDirection.DESC,
) -> PaginatedResponse[SearchResultRead]:
    result = await service.list_for_query(
        session,
        query_id,
        page=page,
        page_size=page_size,
        filters=SearchResultFilters(
            source_domain=source_domain,
            is_duplicate=is_duplicate,
            min_pre_score=min_pre_score,
        ),
        sort=SearchResultSort(sort_by, sort_direction),
    )
    return _page_response(result, page, page_size)


@job_router.get(
    "/{job_id}/search-results",
    response_model=PaginatedResponse[SearchResultRead],
    responses=ERROR_RESPONSES,
)
async def list_job_results(
    job_id: Annotated[UUID, Path()],
    session: SessionDependency,
    service: SearchResultImportServiceDependency,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    query_id: UUID | None = None,
    source_domain: str | None = None,
    is_duplicate: bool | None = None,
    language: SearchLanguage | None = None,
    query_type: QueryType | None = None,
    min_pre_score: Annotated[float | None, Query(ge=0, le=100)] = None,
    candidate_assigned: bool | None = None,
    sort_by: SearchResultSortField = SearchResultSortField.DISCOVERED_AT,
    sort_direction: SortDirection = SortDirection.DESC,
) -> PaginatedResponse[SearchResultRead]:
    result = await service.list_for_job(
        session,
        job_id,
        page=page,
        page_size=page_size,
        filters=SearchResultFilters(
            query_id,
            source_domain,
            is_duplicate,
            min_pre_score,
            candidate_assigned,
            language,
            query_type,
        ),
        sort=SearchResultSort(sort_by, sort_direction),
    )
    return _page_response(result, page, page_size)


@result_router.get("/{result_id}", response_model=SearchResultRead, responses=ERROR_RESPONSES)
async def get_result(
    result_id: Annotated[UUID, Path()],
    session: SessionDependency,
    service: SearchResultImportServiceDependency,
) -> SearchResultRead:
    return SearchResultRead.model_validate(await service.get(session, result_id))


@result_router.delete(
    "/{result_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    responses=ERROR_RESPONSES,
)
async def delete_result(
    result_id: Annotated[UUID, Path()],
    session: SessionDependency,
    service: SearchResultImportServiceDependency,
) -> Response:
    await service.delete(session, result_id)
    logger.info("search_result_deleted", result_id=str(result_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
