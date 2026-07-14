from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Path, Request

from app.api.v1.candidates import candidate_read
from app.api.v1.enrichment import diff_read
from app.dependencies import LinkedInEnrichmentServiceDependency, SessionDependency
from app.domain.candidates.types import CandidateWithCounts
from app.schemas.enrichment import CandidateEnrichmentImportResponse, CandidateEnrichmentRunRead
from app.schemas.linkedin_enrichment import LinkedInEnrichmentRequest

router = APIRouter()


@router.post(
    "/candidates/{candidate_id}/enrichment/linkedin",
    response_model=CandidateEnrichmentImportResponse,
)
async def enrich_linkedin(
    candidate_id: Annotated[UUID, Path()],
    payload: LinkedInEnrichmentRequest,
    request: Request,
    session: SessionDependency,
    service: LinkedInEnrichmentServiceDependency,
) -> CandidateEnrichmentImportResponse:
    outcome = await service.enrich_candidate(session, candidate_id, payload)
    candidate = outcome.candidate
    record = CandidateWithCounts(
        candidate,
        len(candidate.experiences),
        len(candidate.educations),
        len(candidate.skills),
        len(candidate.certifications),
        len(candidate.languages),
    )
    return CandidateEnrichmentImportResponse(
        candidate=candidate_read(record),
        run=CandidateEnrichmentRunRead.model_validate(outcome.run),
        mode=payload.mode,
        import_mode=payload.import_mode,
        identity_update_strategy=payload.identity_update_strategy,
        data_quality_before=outcome.quality_before,
        data_quality_after=candidate.data_quality_score,
        profile_status_before=outcome.profile_status_before,
        profile_status_after=candidate.profile_status,
        diff=diff_read(outcome.diff),
        warnings=list(outcome.diff.warnings),
    )
