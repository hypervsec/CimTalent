from __future__ import annotations

from dataclasses import asdict
from typing import Any, cast
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.domain.enrichment.enums import EnrichmentProvider, EnrichmentSection
from app.domain.enrichment.types import CandidateEnrichmentRequest, CandidateEnrichmentResult
from app.domain.linkedin.enums import LinkedInProviderMode
from app.domain.linkedin.exceptions import LinkedInProviderDisabledError
from app.integrations.linkedin.fixture_provider import LinkedInFixtureEnrichmentProvider
from app.integrations.linkedin.provider import LinkedInEnrichmentProvider
from app.schemas.enrichment import CandidateEnrichmentImportRequest
from app.schemas.linkedin_enrichment import LinkedInEnrichmentRequest
from app.services.candidate_enrichment import CandidateEnrichmentService, EnrichmentOutcome


class LinkedInCandidateEnrichmentService:
    def __init__(self, enrichment_service: CandidateEnrichmentService, settings: Settings) -> None:
        self.enrichment_service = enrichment_service
        self.settings = settings

    async def enrich_candidate(
        self, session: AsyncSession, candidate_id: UUID, payload: LinkedInEnrichmentRequest
    ) -> EnrichmentOutcome:
        candidate = await self.enrichment_service._load_candidate(session, candidate_id)
        if not candidate.normalized_profile_url and not candidate.primary_profile_url:
            from app.domain.linkedin.exceptions import LinkedInProfileUrlInvalidError

            raise LinkedInProfileUrlInvalidError("Candidate has no LinkedIn profile URL.")
        profile_url = candidate.normalized_profile_url or candidate.primary_profile_url
        sections = tuple(payload.requested_sections or self._default_sections(payload))
        request = CandidateEnrichmentRequest(
            candidate_id, profile_url, payload.mode, sections, payload.fixture_key
        )
        if payload.provider_mode is LinkedInProviderMode.FIXTURE:
            if not self.settings.enable_linkedin_fixture_provider:
                raise LinkedInProviderDisabledError("Fixture provider is disabled.")
            result = await LinkedInFixtureEnrichmentProvider(self.settings).enrich(request)
        else:
            if not self.settings.enable_linkedin_profile_scraping:
                raise LinkedInProviderDisabledError("Live LinkedIn profile scraping is disabled.")
            from app.core.browser.manager import BrowserManager

            result = await LinkedInEnrichmentProvider(
                BrowserManager(self.settings), settings=self.settings
            ).enrich(request)
        import_payload = self._to_import_payload(result, payload)
        return await self.enrichment_service.import_enrichment(
            session, candidate_id, import_payload, allow_linkedin=True
        )

    @staticmethod
    def _default_sections(payload: LinkedInEnrichmentRequest) -> tuple[EnrichmentSection, ...]:
        base = [
            EnrichmentSection.IDENTITY,
            EnrichmentSection.ABOUT,
            EnrichmentSection.EXPERIENCE,
            EnrichmentSection.EDUCATION,
            EnrichmentSection.SKILLS,
        ]
        if payload.mode.value == "deep":
            base.extend([EnrichmentSection.CERTIFICATIONS, EnrichmentSection.LANGUAGES])
        return tuple(base)

    @staticmethod
    def _to_import_payload(
        result: CandidateEnrichmentResult, request: LinkedInEnrichmentRequest
    ) -> CandidateEnrichmentImportRequest:
        identity = None
        if result.identity:
            identity = {
                name: asdict(value)
                for name in (
                    "full_name",
                    "headline",
                    "about",
                    "location_raw",
                    "city",
                    "country",
                    "current_title",
                    "current_company",
                    "open_to_work",
                )
                if (value := getattr(result.identity, name)) is not None
            }

        def row(item: object) -> dict[str, object]:
            return cast(dict[str, object], asdict(cast(Any, item)))

        experiences = [row(item) for item in result.experiences]
        for item in experiences:
            item.pop("position_title_normalized", None)
        educations = [row(item) for item in result.educations]
        for item in educations:
            item.pop("field_of_study_normalized", None)
        skills = [row(item) for item in result.skills]
        for item in skills:
            item.pop("normalized_name", None)
        languages = [row(item) for item in result.languages]
        for item in languages:
            item.pop("language_normalized", None)
        return CandidateEnrichmentImportRequest.model_validate(
            {
                "provider": EnrichmentProvider.LINKEDIN,
                "mode": request.mode,
                "import_mode": request.import_mode,
                "identity_update_strategy": request.identity_update_strategy,
                "identity": identity,
                "experiences": experiences,
                "educations": educations,
                "skills": skills,
                "certifications": [row(item) for item in result.certifications],
                "languages": languages,
                "parser_version": result.parser_version,
                "warnings": list(result.warnings),
                "is_partial": result.is_partial,
            }
        )
