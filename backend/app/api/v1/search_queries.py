from math import ceil
from time import perf_counter
from typing import Annotated, Any
from uuid import UUID

import structlog
from fastapi import APIRouter, Path, Query, Request, Response, status

from app.db.enums import SearchLanguage, SearchSource, SearchStatus
from app.dependencies import QueryGenerationServiceDependency, SessionDependency
from app.domain.jobs.types import SortDirection
from app.domain.sourcing.types import (
    QueryType,
    SearchQueryFilters,
    SearchQuerySort,
    SearchQuerySortField,
)
from app.schemas.common import ErrorResponse, PaginatedResponse
from app.schemas.search_queries import (
    GeneratedQueryRead,
    GenerateQueriesRequest,
    GenerateQueriesResponse,
)

job_router = APIRouter(prefix="/jobs")
query_router = APIRouter(prefix="/queries")
logger = structlog.get_logger(__name__)
ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    404: {"model": ErrorResponse},
    409: {"model": ErrorResponse},
    422: {"description": "Query generation validation failed."},
    500: {"model": ErrorResponse},
}


@job_router.post(
    "/{job_id}/queries/generate",
    response_model=GenerateQueriesResponse,
    responses=ERROR_RESPONSES,
)
async def generate_queries(
    job_id: Annotated[UUID, Path()],
    payload: GenerateQueriesRequest,
    request: Request,
    session: SessionDependency,
    service: QueryGenerationServiceDependency,
) -> GenerateQueriesResponse:
    started_at = perf_counter()
    logger.info(
        "query_generation_started",
        request_id=request.state.request_id,
        job_id=str(job_id),
    )
    outcome = await service.generate(
        session,
        job_id,
        max_queries=payload.max_queries,
        languages=tuple(payload.languages),
        target_domain=payload.target_domain,
    )
    logger.info(
        "query_generation_completed",
        request_id=request.state.request_id,
        job_id=str(job_id),
        generated_count=outcome.generated_count,
        created_count=outcome.created_count,
        duration_ms=round((perf_counter() - started_at) * 1000, 2),
        status_code=status.HTTP_200_OK,
    )
    return GenerateQueriesResponse(
        job_id=outcome.job_id,
        generated_count=outcome.generated_count,
        created_count=outcome.created_count,
        existing_count=outcome.existing_count,
        skipped_count=outcome.skipped_count,
        queries=[GeneratedQueryRead.model_validate(item) for item in outcome.queries],
    )


@job_router.get(
    "/{job_id}/queries",
    response_model=PaginatedResponse[GeneratedQueryRead],
    responses=ERROR_RESPONSES,
)
async def list_queries(
    job_id: Annotated[UUID, Path()],
    session: SessionDependency,
    service: QueryGenerationServiceDependency,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    source: SearchSource | None = None,
    language: SearchLanguage | None = None,
    query_status: Annotated[SearchStatus | None, Query(alias="status")] = None,
    query_type: QueryType | None = None,
    precision_level: Annotated[int | None, Query(ge=1, le=5)] = None,
    sort_by: SearchQuerySortField = SearchQuerySortField.CREATED_AT,
    sort_direction: SortDirection = SortDirection.DESC,
) -> PaginatedResponse[GeneratedQueryRead]:
    result = await service.list_for_job(
        session,
        job_id,
        page=page,
        page_size=page_size,
        filters=SearchQueryFilters(source, language, query_status, query_type, precision_level),
        sort=SearchQuerySort(sort_by, sort_direction),
    )
    total_pages = ceil(result.total_items / page_size) if result.total_items else 0
    return PaginatedResponse[GeneratedQueryRead](
        items=[GeneratedQueryRead.model_validate(item) for item in result.items],
        page=page,
        page_size=page_size,
        total_items=result.total_items,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_previous=page > 1,
    )


@query_router.get("/{query_id}", response_model=GeneratedQueryRead, responses=ERROR_RESPONSES)
async def get_query(
    query_id: Annotated[UUID, Path()],
    session: SessionDependency,
    service: QueryGenerationServiceDependency,
) -> GeneratedQueryRead:
    return GeneratedQueryRead.model_validate(await service.get(session, query_id))


@query_router.delete(
    "/{query_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    responses=ERROR_RESPONSES,
)
async def delete_query(
    query_id: Annotated[UUID, Path()],
    session: SessionDependency,
    service: QueryGenerationServiceDependency,
) -> Response:
    await service.delete(session, query_id)
    logger.info("search_query_deleted", query_id=str(query_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
