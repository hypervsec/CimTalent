from datetime import datetime
from time import perf_counter
from typing import Annotated, Any
from uuid import UUID

import structlog
from fastapi import APIRouter, Path, Query, Request, Response, status

from app.db.enums import JobSource, JobStatus
from app.dependencies import JobParsingServiceDependency, JobServiceDependency, SessionDependency
from app.domain.jobs import (
    EmptyJobDescriptionError,
    JobListFilters,
    JobNotFoundError,
    JobParseStateError,
    JobParsingError,
    JobSort,
    JobSortField,
    JobWithCounts,
    SortDirection,
)
from app.domain.jobs.exceptions import JobDomainError
from app.schemas.common import ErrorResponse, PaginatedResponse
from app.schemas.job_parsing import ParsedRequirementRead, ParseJobResult
from app.schemas.jobs import JobCreate, JobListItem, JobRead, JobRequirementRead, JobUpdate

router = APIRouter(prefix="/jobs")
logger = structlog.get_logger(__name__)

ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    404: {"model": ErrorResponse, "description": "Job posting was not found."},
    409: {"model": ErrorResponse, "description": "The operation conflicts with job state."},
    422: {"description": "Request or domain validation failed."},
    500: {"model": ErrorResponse, "description": "Internal persistence error."},
}


def _count_values(record: JobWithCounts) -> dict[str, int]:
    return {
        "requirement_count": record.requirement_count,
        "search_query_count": record.search_query_count,
        "candidate_match_count": record.candidate_match_count,
        "shortlist_count": record.shortlist_count,
    }


def _job_read(record: JobWithCounts) -> JobRead:
    return JobRead.model_validate(record.job).model_copy(update=_count_values(record))


def _job_list_item(record: JobWithCounts) -> JobListItem:
    return JobListItem.model_validate(record.job).model_copy(update=_count_values(record))


def _log(
    request: Request,
    event: str,
    started_at: float,
    status_code: int,
    job_id: UUID | None = None,
) -> None:
    logger.info(
        event,
        request_id=request.state.request_id,
        job_id=str(job_id) if job_id is not None else None,
        duration_ms=round((perf_counter() - started_at) * 1000, 2),
        status_code=status_code,
    )


@router.post(
    "",
    response_model=JobRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a job posting",
    responses=ERROR_RESPONSES,
)
async def create_job(
    payload: JobCreate,
    request: Request,
    session: SessionDependency,
    service: JobServiceDependency,
) -> JobRead:
    started_at = perf_counter()
    record = await service.create_job(session, data=payload.model_dump(mode="python"))
    _log(request, "job_created", started_at, status.HTTP_201_CREATED, record.job.id)
    return _job_read(record)


@router.get(
    "",
    response_model=PaginatedResponse[JobListItem],
    summary="List job postings",
    responses={500: ERROR_RESPONSES[500]},
)
async def list_jobs(
    request: Request,
    session: SessionDependency,
    service: JobServiceDependency,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    job_status: Annotated[JobStatus | None, Query(alias="status")] = None,
    source: JobSource | None = None,
    city: str | None = None,
    company_name: str | None = None,
    title: str | None = None,
    search: str | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    sort_by: JobSortField = JobSortField.CREATED_AT,
    sort_direction: SortDirection = SortDirection.DESC,
) -> PaginatedResponse[JobListItem]:
    started_at = perf_counter()
    page_data = await service.list_jobs(
        session,
        page=page,
        page_size=page_size,
        filters=JobListFilters(
            status=job_status,
            source=source,
            city=city,
            company_name=company_name,
            title=title,
            search=search,
            created_from=created_from,
            created_to=created_to,
        ),
        sort=JobSort(sort_by, sort_direction),
    )
    response = PaginatedResponse[JobListItem](
        items=[_job_list_item(record) for record in page_data.items],
        page=page_data.page,
        page_size=page_data.page_size,
        total_items=page_data.total_items,
        total_pages=page_data.total_pages,
        has_next=page_data.has_next,
        has_previous=page_data.has_previous,
    )
    _log(request, "job_listed", started_at, status.HTTP_200_OK)
    return response


@router.get(
    "/{job_id}",
    response_model=JobRead,
    summary="Get a job posting",
    responses=ERROR_RESPONSES,
)
async def get_job(
    job_id: Annotated[UUID, Path()],
    request: Request,
    session: SessionDependency,
    service: JobServiceDependency,
) -> JobRead:
    started_at = perf_counter()
    record = await service.get_job(session, job_id)
    _log(request, "job_retrieved", started_at, status.HTTP_200_OK, job_id)
    return _job_read(record)


@router.patch(
    "/{job_id}",
    response_model=JobRead,
    summary="Update a job posting",
    responses=ERROR_RESPONSES,
)
async def update_job(
    job_id: Annotated[UUID, Path()],
    payload: JobUpdate,
    request: Request,
    session: SessionDependency,
    service: JobServiceDependency,
) -> JobRead:
    started_at = perf_counter()
    record = await service.update_job(
        session,
        job_id,
        changes=payload.model_dump(mode="python", exclude_unset=True),
    )
    _log(request, "job_updated", started_at, status.HTTP_200_OK, job_id)
    return _job_read(record)


@router.delete(
    "/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Delete a job posting",
    responses=ERROR_RESPONSES,
)
async def delete_job(
    job_id: Annotated[UUID, Path()],
    request: Request,
    session: SessionDependency,
    service: JobServiceDependency,
) -> Response:
    started_at = perf_counter()
    await service.delete_job(session, job_id)
    _log(request, "job_deleted", started_at, status.HTTP_204_NO_CONTENT, job_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{job_id}/requirements",
    response_model=list[JobRequirementRead],
    summary="List extracted job requirements",
    responses=ERROR_RESPONSES,
)
async def list_job_requirements(
    job_id: Annotated[UUID, Path()],
    request: Request,
    session: SessionDependency,
    service: JobServiceDependency,
) -> list[JobRequirementRead]:
    started_at = perf_counter()
    requirements = await service.get_job_requirements(session, job_id)
    _log(request, "job_requirements_listed", started_at, status.HTTP_200_OK, job_id)
    return [JobRequirementRead.model_validate(item) for item in requirements]


def _parse_error_status(error: JobDomainError) -> int:
    if isinstance(error, JobNotFoundError):
        return status.HTTP_404_NOT_FOUND
    if isinstance(error, JobParseStateError):
        return status.HTTP_409_CONFLICT
    if isinstance(error, (EmptyJobDescriptionError, JobParsingError)):
        return status.HTTP_422_UNPROCESSABLE_CONTENT
    return status.HTTP_500_INTERNAL_SERVER_ERROR


@router.post(
    "/{job_id}/parse",
    response_model=ParseJobResult,
    summary="Parse a job posting into normalized requirements",
    responses=ERROR_RESPONSES,
)
async def parse_job(
    job_id: Annotated[UUID, Path()],
    request: Request,
    session: SessionDependency,
    service: JobParsingServiceDependency,
) -> ParseJobResult:
    started_at = perf_counter()
    logger.info(
        "job_parse_started",
        request_id=request.state.request_id,
        job_id=str(job_id),
        parser_version=service.parser.version,
    )
    try:
        outcome = await service.parse_job(session, job_id)
    except JobDomainError as error:
        logger.warning(
            "job_parse_failed",
            request_id=request.state.request_id,
            job_id=str(job_id),
            parser_version=service.parser.version,
            duration_ms=round((perf_counter() - started_at) * 1000, 2),
            status_code=_parse_error_status(error),
        )
        raise
    parsed = outcome.parsed_data
    logger.info(
        "job_parse_completed",
        request_id=request.state.request_id,
        job_id=str(job_id),
        parser_version=parsed.parser_version,
        requirement_count=outcome.created_requirement_count,
        warning_count=len(parsed.warnings),
        confidence=parsed.confidence,
        duration_ms=round((perf_counter() - started_at) * 1000, 2),
        status_code=status.HTTP_200_OK,
    )
    return ParseJobResult(
        job_id=outcome.job_id,
        status=outcome.status,
        parser_version=parsed.parser_version,
        created_requirement_count=outcome.created_requirement_count,
        updated_job_fields=outcome.updated_job_fields,
        warnings=parsed.warnings,
        confidence=parsed.confidence,
        requirements=tuple(
            ParsedRequirementRead.model_validate(requirement) for requirement in parsed.requirements
        ),
    )
