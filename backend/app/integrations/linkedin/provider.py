from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

from bs4 import BeautifulSoup

from app.config import Settings
from app.core.browser.manager import BrowserManager
from app.domain.enrichment.enums import EnrichmentMode
from app.domain.enrichment.exceptions import UnsupportedEnrichmentProviderError
from app.domain.enrichment.types import (
    CandidateEnrichmentRequest,
    CandidateEnrichmentResult,
)
from app.domain.linkedin.constants import PARSER_VERSION
from app.domain.linkedin.types import ParserLimits
from app.integrations.linkedin.navigator import LinkedInProfileNavigator
from app.integrations.linkedin.parser_context import ParserContext
from app.integrations.linkedin.parsers import (
    AboutParser,
    CertificationsParser,
    EducationParser,
    ExperienceParser,
    LanguagesParser,
    SkillsParser,
    TopCardParser,
)
from app.integrations.linkedin.selector_registry import SelectorRegistry


class LinkedInEnrichmentProvider:
    def __init__(
        self,
        browser: BrowserManager,
        *,
        navigator: LinkedInProfileNavigator | None = None,
        selectors: SelectorRegistry | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.browser = browser
        self.navigator = navigator or LinkedInProfileNavigator(browser)
        self.selectors = selectors or SelectorRegistry()
        self.settings = settings or browser.settings

    async def enrich(self, request: CandidateEnrichmentRequest) -> CandidateEnrichmentResult:
        if not self.settings.enable_linkedin_profile_scraping:
            raise UnsupportedEnrichmentProviderError("Live LinkedIn profile scraping is disabled.")
        if not request.profile_url:
            raise ValueError("A LinkedIn profile URL is required.")
        started = datetime.now(UTC)
        async with self.browser.session_page(
            require_session=True, correlation_id=request.correlation_id
        ) as page:
            await self.navigator.open_profile(page, request.profile_url)
            content = await page.content()
            result = self._parse(content, request, request.profile_url)
        return replace(result, started_at=started, completed_at=datetime.now(UTC))

    def _parse(
        self, html: str, request: CandidateEnrichmentRequest, source_url: str
    ) -> CandidateEnrichmentResult:
        soup = BeautifulSoup(html, "html.parser")
        limits = self._limits(request.mode)
        context = ParserContext(
            soup,
            source_url,
            None,
            request.mode,
            self.selectors,
            PARSER_VERSION,
            limits,
            request.correlation_id,
        )
        top = TopCardParser().parse(context)
        identity = top.value
        warnings = list(top.warnings)
        about = AboutParser().parse(context)
        if about.value and identity:
            identity = replace(identity, about=about.value)
        warnings.extend(about.warnings)
        experiences = (
            ExperienceParser().parse(context)
            if "experience" in request.requested_sections
            else None
        )
        educations = (
            EducationParser().parse(context) if "education" in request.requested_sections else None
        )
        skills = SkillsParser().parse(context) if "skills" in request.requested_sections else None
        certifications = (
            CertificationsParser().parse(context)
            if "certifications" in request.requested_sections
            else None
        )
        languages = (
            LanguagesParser().parse(context) if "languages" in request.requested_sections else None
        )
        for parsed in (experiences, educations, skills, certifications, languages):
            if parsed:
                warnings.extend(parsed.warnings)
        if identity is None:
            raise ValueError("LinkedIn profile identity could not be parsed.")
        return CandidateEnrichmentResult(
            provider=__import__(
                "app.domain.enrichment.enums", fromlist=["EnrichmentProvider"]
            ).EnrichmentProvider.LINKEDIN,
            mode=request.mode,
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            source_url=source_url,
            identity=identity,
            experiences=experiences.items if experiences else (),
            educations=educations.items if educations else (),
            skills=skills.items if skills else (),
            certifications=certifications.items if certifications else (),
            languages=languages.items if languages else (),
            warnings=tuple(warnings),
            parser_version=PARSER_VERSION,
            is_partial=bool(warnings) or request.mode is EnrichmentMode.FAST,
            provider_metadata={
                "selector_profile": self.settings.linkedin_selector_profile,
                "sections_attempted": [x.value for x in request.requested_sections],
            },
        )

    def _limits(self, mode: EnrichmentMode) -> ParserLimits:
        from app.domain.linkedin.types import ParserLimits

        return ParserLimits(
            self.settings.linkedin_max_experiences_fast
            if mode is EnrichmentMode.FAST
            else self.settings.linkedin_max_experiences_deep,
            self.settings.linkedin_max_educations,
            self.settings.linkedin_max_skills,
            self.settings.linkedin_max_certifications,
            self.settings.linkedin_max_languages,
        )
