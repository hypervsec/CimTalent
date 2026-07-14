from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

import structlog
from fastapi import APIRouter, Path, Query, Request

from app.api.v1.candidates import candidate_read
from app.dependencies import CandidateEnrichmentServiceDependency, SessionDependency
from app.domain.candidates.quality import CandidateQualityInput, calculate_candidate_quality
from app.domain.candidates.types import CandidateWithCounts
from app.domain.enrichment.diff import CandidateEnrichmentDiff, CollectionDiff
from app.domain.enrichment.enums import (
    CandidateEnrichmentStatus,
    EnrichmentMode,
    EnrichmentProvider,
)
from app.domain.jobs.types import SortDirection
from app.schemas.candidates import CandidateQualityRead
from app.schemas.common import ErrorResponse
from app.schemas.enrichment import (
    CandidateCertificationRead,
    CandidateEducationRead,
    CandidateEnrichmentDiffRead,
    CandidateEnrichmentImportRequest,
    CandidateEnrichmentImportResponse,
    CandidateEnrichmentPreviewResponse,
    CandidateEnrichmentRunPage,
    CandidateEnrichmentRunRead,
    CandidateExperienceRead,
    CandidateLanguageRead,
    CandidateProfileSnapshotRead,
    CandidateSkillRead,
    EnrichmentCollectionDiffRead,
    EnrichmentIdentityChangeRead,
)

router = APIRouter()
logger = structlog.get_logger(__name__)
ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    404: {"model": ErrorResponse},
    409: {"model": ErrorResponse},
    413: {"model": ErrorResponse},
    422: {"description": "Enrichment validation failed."},
    500: {"model": ErrorResponse},
}


def _collection_read(value: CollectionDiff) -> EnrichmentCollectionDiffRead:
    return EnrichmentCollectionDiffRead.model_validate(value, from_attributes=True)


def diff_read(value: CandidateEnrichmentDiff) -> CandidateEnrichmentDiffRead:
    return CandidateEnrichmentDiffRead(
        identity_changes=[
            EnrichmentIdentityChangeRead.model_validate(item, from_attributes=True)
            for item in value.identity_changes
        ],
        experiences=_collection_read(value.experiences),
        educations=_collection_read(value.educations),
        skills=_collection_read(value.skills),
        certifications=_collection_read(value.certifications),
        languages=_collection_read(value.languages),
        predicted_quality_before=value.predicted_quality_before,
        predicted_quality_after=value.predicted_quality_after,
        warnings=list(value.warnings),
    )


@router.post(
    "/candidates/{candidate_id}/enrichment/preview",
    response_model=CandidateEnrichmentPreviewResponse,
    responses=ERROR_RESPONSES,
)
async def preview_candidate_enrichment(
    candidate_id: Annotated[UUID, Path()],
    payload: CandidateEnrichmentImportRequest,
    request: Request,
    session: SessionDependency,
    service: CandidateEnrichmentServiceDependency,
) -> CandidateEnrichmentPreviewResponse:
    diff = await service.preview_import(session, candidate_id, payload)
    logger.info(
        "candidate_enrichment_previewed",
        request_id=request.state.request_id,
        candidate_id=str(candidate_id),
        provider=payload.provider.value,
        mode=payload.mode.value,
        import_mode=payload.import_mode.value,
    )
    return CandidateEnrichmentPreviewResponse(
        candidate_id=candidate_id,
        mode=payload.mode,
        import_mode=payload.import_mode,
        identity_update_strategy=payload.identity_update_strategy,
        diff=diff_read(diff),
        warnings=payload.warnings,
    )


@router.post(
    "/candidates/{candidate_id}/enrichment/import",
    response_model=CandidateEnrichmentImportResponse,
    responses=ERROR_RESPONSES,
)
async def import_candidate_enrichment(
    candidate_id: Annotated[UUID, Path()],
    payload: CandidateEnrichmentImportRequest,
    request: Request,
    session: SessionDependency,
    service: CandidateEnrichmentServiceDependency,
) -> CandidateEnrichmentImportResponse:
    outcome = await service.import_enrichment(session, candidate_id, payload)
    record = CandidateWithCounts(
        outcome.candidate,
        len(outcome.candidate.experiences),
        len(outcome.candidate.educations),
        len(outcome.candidate.skills),
        len(outcome.candidate.certifications),
        len(outcome.candidate.languages),
    )
    logger.info(
        "candidate_enrichment_completed",
        request_id=request.state.request_id,
        candidate_id=str(candidate_id),
        run_id=str(outcome.run.id),
        provider=payload.provider.value,
        mode=payload.mode.value,
        import_mode=payload.import_mode.value,
        quality_before=outcome.quality_before,
        quality_after=outcome.candidate.data_quality_score,
    )
    return CandidateEnrichmentImportResponse(
        candidate=candidate_read(record),
        run=CandidateEnrichmentRunRead.model_validate(outcome.run),
        mode=payload.mode,
        import_mode=payload.import_mode,
        identity_update_strategy=payload.identity_update_strategy,
        data_quality_before=outcome.quality_before,
        data_quality_after=outcome.candidate.data_quality_score,
        profile_status_before=outcome.profile_status_before,
        profile_status_after=outcome.candidate.profile_status,
        diff=diff_read(outcome.diff),
        warnings=payload.warnings,
    )


@router.get(
    "/candidates/{candidate_id}/enrichment-runs",
    response_model=CandidateEnrichmentRunPage,
    responses=ERROR_RESPONSES,
)
async def list_candidate_enrichment_runs(
    candidate_id: Annotated[UUID, Path()],
    session: SessionDependency,
    service: CandidateEnrichmentServiceDependency,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    provider: EnrichmentProvider | None = None,
    mode: EnrichmentMode | None = None,
    run_status: Annotated[CandidateEnrichmentStatus | None, Query(alias="status")] = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    sort_by: Annotated[str, Query(pattern="^(created_at|completed_at|status)$")] = "created_at",
    sort_direction: SortDirection = SortDirection.DESC,
) -> CandidateEnrichmentRunPage:
    items, total = await service.list_candidate_runs(
        session,
        candidate_id,
        offset=(page - 1) * page_size,
        limit=page_size,
        provider=provider,
        mode=mode,
        status=run_status,
        created_from=created_from,
        created_to=created_to,
        sort_by=sort_by,
        descending=sort_direction is SortDirection.DESC,
    )
    return CandidateEnrichmentRunPage(
        items=[CandidateEnrichmentRunRead.model_validate(item) for item in items],
        page=page,
        page_size=page_size,
        total_items=total,
        total_pages=(total + page_size - 1) // page_size if total else 0,
    )


@router.get(
    "/enrichment-runs/{run_id}",
    response_model=CandidateEnrichmentRunRead,
    responses=ERROR_RESPONSES,
)
async def get_enrichment_run(
    run_id: Annotated[UUID, Path()],
    session: SessionDependency,
    service: CandidateEnrichmentServiceDependency,
) -> CandidateEnrichmentRunRead:
    return CandidateEnrichmentRunRead.model_validate(await service.get_run(session, run_id))


@router.get(
    "/candidates/{candidate_id}/profile",
    response_model=CandidateProfileSnapshotRead,
    responses=ERROR_RESPONSES,
)
async def get_candidate_profile(
    candidate_id: Annotated[UUID, Path()],
    session: SessionDependency,
    service: CandidateEnrichmentServiceDependency,
) -> CandidateProfileSnapshotRead:
    candidate = await service.get_profile(session, candidate_id)
    record = CandidateWithCounts(
        candidate,
        len(candidate.experiences),
        len(candidate.educations),
        len(candidate.skills),
        len(candidate.certifications),
        len(candidate.languages),
    )
    quality = calculate_candidate_quality(
        CandidateQualityInput(
            full_name=candidate.full_name,
            normalized_profile_url=candidate.normalized_profile_url,
            headline=candidate.headline,
            location_raw=candidate.location_raw,
            city=candidate.city,
            country=candidate.country,
            current_title=candidate.current_title,
            current_company=candidate.current_company,
            about=candidate.about,
            discovery_snippet=candidate.discovery_snippet,
            experience_count=len(candidate.experiences),
            education_count=len(candidate.educations),
            skill_count=len(candidate.skills),
        )
    )
    latest = candidate.enrichment_runs[0] if candidate.enrichment_runs else None
    return CandidateProfileSnapshotRead(
        candidate=candidate_read(record),
        experiences=[
            CandidateExperienceRead.model_validate(item) for item in candidate.experiences
        ],
        educations=[CandidateEducationRead.model_validate(item) for item in candidate.educations],
        skills=[CandidateSkillRead.model_validate(item) for item in candidate.skills],
        certifications=[
            CandidateCertificationRead.model_validate(item) for item in candidate.certifications
        ],
        languages=[CandidateLanguageRead.model_validate(item) for item in candidate.languages],
        quality=CandidateQualityRead(
            candidate_id=candidate.id,
            total_score=quality.total_score,
            field_scores=quality.field_scores,
            missing_fields=quality.missing_fields,
            warnings=quality.warnings,
        ),
        latest_enrichment_run=(
            CandidateEnrichmentRunRead.model_validate(latest) if latest else None
        ),
    )
