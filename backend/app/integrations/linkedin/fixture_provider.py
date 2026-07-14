from __future__ import annotations

from pathlib import Path

from app.config import Settings
from app.core.browser.manager import BrowserManager
from app.domain.enrichment.types import CandidateEnrichmentRequest, CandidateEnrichmentResult
from app.integrations.linkedin.provider import LinkedInEnrichmentProvider


class LinkedInFixtureEnrichmentProvider:
    def __init__(self, settings: Settings, *, browser: BrowserManager | None = None) -> None:
        self.settings = settings
        self.browser = browser

    async def enrich(self, request: CandidateEnrichmentRequest) -> CandidateEnrichmentResult:
        key = request.correlation_id or "software_engineer_en"
        if ".." in Path(key).parts or "/" in key or "\\" in key:
            raise ValueError("Invalid fixture key.")
        if not self.settings.enable_linkedin_fixture_provider:
            raise ValueError("Fixture provider is disabled.")
        path = self.settings.linkedin_fixture_dir / f"{key}.html"
        if not path.is_file():
            raise FileNotFoundError(f"Fixture profile was not found: {key}")
        html = path.read_text(encoding="utf-8")
        if self.browser is None:
            from app.core.browser.manager import BrowserManager

            self.browser = BrowserManager(self.settings)
        provider = LinkedInEnrichmentProvider(self.browser, settings=self.settings)
        return provider._parse(
            html, request, request.profile_url or "https://www.linkedin.com/in/fixture"
        )
