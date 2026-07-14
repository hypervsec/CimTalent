from typing import cast

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from app.domain.candidates import (
    CandidateDomainError,
    CandidateMergeConflictError,
    CandidateMergeError,
    CandidateNotFoundError,
    CandidatePersistenceError,
    CandidateValidationError,
    DuplicateCandidateError,
    InvalidCandidateStatusTransitionError,
    SearchResultNotEligibleError,
)
from app.domain.enrichment.exceptions import (
    CandidateEnrichmentPersistenceError,
    CandidateEnrichmentStateError,
    CandidateEnrichmentValidationError,
    EnrichmentConflictError,
    EnrichmentDomainError,
    EnrichmentNormalizationError,
    EnrichmentPayloadTooLargeError,
    EnrichmentRunNotFoundError,
    UnsupportedEnrichmentProviderError,
)
from app.domain.jobs import (
    DuplicateJobError,
    EmptyJobDescriptionError,
    InvalidJobStatusTransitionError,
    JobConflictError,
    JobNotFoundError,
    JobParseStateError,
    JobParsingError,
    JobPersistenceError,
    JobValidationError,
    RequirementPersistenceError,
)
from app.domain.jobs.exceptions import JobDomainError
from app.domain.sourcing import (
    DuplicateSearchQueryError,
    InvalidTargetDomainError,
    JobNotParsedError,
    JobQueryGenerationStateError,
    ManualImportPayloadTooLargeError,
    ManualImportValidationError,
    QueryGenerationError,
    SearchQueryNotFoundError,
    SearchQueryPersistenceError,
    SearchResultNotFoundError,
    SearchResultParsingError,
    SearchResultPersistenceError,
)
from app.schemas.common import ErrorDetail, ErrorResponse

logger = structlog.get_logger(__name__)


def request_id_from(request: Request) -> str:
    return cast(str, getattr(request.state, "request_id", "unknown"))


async def job_domain_error_handler(request: Request, error: Exception) -> JSONResponse:
    domain_error = cast(JobDomainError, error)
    status_code = _domain_status_code(domain_error)
    logger.warning(
        domain_error.code,
        request_id=request_id_from(request),
        status_code=status_code,
        details=domain_error.details,
    )
    return _error_response(
        request,
        status_code=status_code,
        code=domain_error.code,
        message=domain_error.message,
        details=domain_error.details,
    )


async def candidate_domain_error_handler(request: Request, error: Exception) -> JSONResponse:
    domain_error = cast(CandidateDomainError, error)
    status_code = _candidate_status_code(domain_error)
    logger.warning(
        domain_error.code,
        request_id=request_id_from(request),
        status_code=status_code,
        details=domain_error.details,
    )
    return _error_response(
        request,
        status_code=status_code,
        code=domain_error.code,
        message=domain_error.message,
        details=domain_error.details,
    )


async def enrichment_domain_error_handler(request: Request, error: Exception) -> JSONResponse:
    domain_error = cast(EnrichmentDomainError, error)
    status_code = _enrichment_status_code(domain_error)
    logger.warning(
        domain_error.code,
        request_id=request_id_from(request),
        status_code=status_code,
        details=domain_error.details,
    )
    return _error_response(
        request,
        status_code=status_code,
        code=domain_error.code,
        message=domain_error.message,
        details=domain_error.details,
    )


async def integrity_error_handler(request: Request, _: Exception) -> JSONResponse:
    return _error_response(
        request,
        status_code=409,
        code="integrity_conflict",
        message="The operation conflicts with persisted data.",
    )


async def unexpected_error_handler(request: Request, _: Exception) -> JSONResponse:
    logger.exception("unhandled_error", request_id=request_id_from(request), status_code=500)
    return _error_response(
        request,
        status_code=500,
        code="internal_server_error",
        message="An unexpected error occurred.",
    )


async def request_validation_error_handler(request: Request, error: Exception) -> JSONResponse:
    validation_error = cast(RequestValidationError, error)
    safe_errors = [
        {
            "location": [str(part) for part in item["loc"]],
            "message": item["msg"],
            "type": item["type"],
        }
        for item in validation_error.errors()
    ]
    return _error_response(
        request,
        status_code=422,
        code="request_validation_error",
        message="Request validation failed.",
        details={"errors": safe_errors},
    )


def register_exception_handlers(application: FastAPI) -> None:
    application.add_exception_handler(JobDomainError, job_domain_error_handler)
    application.add_exception_handler(CandidateDomainError, candidate_domain_error_handler)
    application.add_exception_handler(EnrichmentDomainError, enrichment_domain_error_handler)
    application.add_exception_handler(IntegrityError, integrity_error_handler)
    application.add_exception_handler(RequestValidationError, request_validation_error_handler)
    application.add_exception_handler(Exception, unexpected_error_handler)


def _domain_status_code(error: JobDomainError) -> int:
    if isinstance(error, (JobNotFoundError, SearchQueryNotFoundError, SearchResultNotFoundError)):
        return 404
    if isinstance(error, ManualImportPayloadTooLargeError):
        return 413
    if isinstance(error, JobValidationError):
        return 422
    if isinstance(error, (EmptyJobDescriptionError, JobParsingError)):
        return 422
    if isinstance(
        error,
        (
            InvalidTargetDomainError,
            ManualImportValidationError,
            QueryGenerationError,
            SearchResultParsingError,
        ),
    ):
        return 422
    if isinstance(
        error,
        (
            InvalidJobStatusTransitionError,
            DuplicateJobError,
            JobConflictError,
            JobParseStateError,
            JobNotParsedError,
            JobQueryGenerationStateError,
            DuplicateSearchQueryError,
        ),
    ):
        return 409
    if isinstance(
        error,
        (
            JobPersistenceError,
            RequirementPersistenceError,
            SearchQueryPersistenceError,
            SearchResultPersistenceError,
        ),
    ):
        return 500
    return 500


def _candidate_status_code(error: CandidateDomainError) -> int:
    if isinstance(error, CandidateNotFoundError):
        return 404
    if isinstance(error, (CandidateValidationError, SearchResultNotEligibleError)):
        return 422
    if isinstance(
        error,
        (
            DuplicateCandidateError,
            InvalidCandidateStatusTransitionError,
            CandidateMergeConflictError,
        ),
    ):
        return 409
    if isinstance(error, CandidateMergeError):
        return 422
    if isinstance(error, CandidatePersistenceError):
        return 500
    return 500


def _enrichment_status_code(error: EnrichmentDomainError) -> int:
    if isinstance(error, EnrichmentRunNotFoundError):
        return 404
    if isinstance(error, EnrichmentPayloadTooLargeError):
        return 413
    if isinstance(
        error,
        (
            CandidateEnrichmentValidationError,
            EnrichmentNormalizationError,
            UnsupportedEnrichmentProviderError,
        ),
    ):
        return 422
    if isinstance(error, (CandidateEnrichmentStateError, EnrichmentConflictError)):
        return 409
    if isinstance(error, CandidateEnrichmentPersistenceError):
        return 500
    return 500


def _error_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    details: dict[str, object] | None = None,
) -> JSONResponse:
    response = ErrorResponse(
        error=ErrorDetail(
            code=code,
            message=message,
            details=details,
            request_id=request_id_from(request),
        )
    )
    return JSONResponse(status_code=status_code, content=response.model_dump(mode="json"))
