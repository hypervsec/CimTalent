from pathlib import Path

import pytest

from app.config import Settings
from app.domain.enrichment.enums import EnrichmentMode, EnrichmentSection
from app.domain.enrichment.types import CandidateEnrichmentRequest
from app.integrations.linkedin.fixture_provider import LinkedInFixtureEnrichmentProvider


@pytest.mark.asyncio
async def test_fixture_provider_is_deterministic() -> None:
    settings = Settings(linkedin_fixture_dir=Path("tests/fixtures/linkedin"))
    request = CandidateEnrichmentRequest(
        candidate_id=None,
        profile_url="https://www.linkedin.com/in/demo",
        mode=EnrichmentMode.DEEP,
        requested_sections=(
            EnrichmentSection.IDENTITY,
            EnrichmentSection.EXPERIENCE,
            EnrichmentSection.SKILLS,
        ),
        correlation_id="software_engineer_en",
    )
    provider = LinkedInFixtureEnrichmentProvider(settings)
    first = await provider.enrich(request)
    second = await provider.enrich(request)
    assert first.identity == second.identity
    assert first.experiences == second.experiences
    assert first.skills == second.skills
    assert first.identity and first.identity.full_name.value == "Demo Engineer"
    assert len(first.experiences) == 1
    assert len(first.skills) == 3
