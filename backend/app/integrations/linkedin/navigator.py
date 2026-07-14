from __future__ import annotations

from time import perf_counter
from typing import Protocol

from app.core.browser.manager import BrowserManager, Page
from app.core.browser.page_guard import LinkedInPageGuard
from app.domain.linkedin.enums import LinkedInPageKind
from app.domain.linkedin.types import NavigationResult
from app.integrations.linkedin.url_builder import LinkedInProfileUrlBuilder


class NavigatorPage(Page, Protocol):
    async def evaluate(self, expression: str) -> object: ...
    async def wait_for_selector(self, selector: str, **kwargs: object) -> object: ...
    async def locator(self, selector: str) -> object: ...


class LinkedInProfileNavigator:
    def __init__(
        self,
        browser: BrowserManager,
        *,
        url_builder: LinkedInProfileUrlBuilder | None = None,
        page_guard: LinkedInPageGuard | None = None,
    ) -> None:
        self.browser = browser
        self.url_builder = url_builder or LinkedInProfileUrlBuilder()
        self.page_guard = page_guard or browser.page_guard

    async def open_profile(self, page: Page, profile_url: str) -> NavigationResult:
        return await self._open(
            page, self.url_builder.canonical_profile_url(profile_url), LinkedInPageKind.PROFILE
        )

    async def open_section(self, page: Page, profile_url: str, section: str) -> NavigationResult:
        kind = LinkedInPageKind(section)
        return await self._open(page, self.url_builder.detail_url(profile_url, section), kind)

    async def open_experience_details(self, page: Page, profile_url: str) -> NavigationResult:
        return await self.open_section(page, profile_url, "experience")

    async def open_education_details(self, page: Page, profile_url: str) -> NavigationResult:
        return await self.open_section(page, profile_url, "education")

    async def open_skills_details(self, page: Page, profile_url: str) -> NavigationResult:
        return await self.open_section(page, profile_url, "skills")

    async def open_certifications_details(self, page: Page, profile_url: str) -> NavigationResult:
        return await self.open_section(page, profile_url, "certifications")

    async def open_languages_details(self, page: Page, profile_url: str) -> NavigationResult:
        return await self.open_section(page, profile_url, "languages")

    async def _open(self, page: Page, url: str, kind: LinkedInPageKind) -> NavigationResult:
        started = perf_counter()
        await self.browser.navigate(page, url)
        return NavigationResult(
            url, page.url, kind, True, elapsed_ms=(perf_counter() - started) * 1000
        )

    async def wait_for_profile_shell(self, page: NavigatorPage) -> None:
        await page.wait_for_selector(
            "main", timeout=self.browser.settings.linkedin_section_timeout_ms
        )

    async def wait_for_section_content(self, page: NavigatorPage, selector: str) -> None:
        await page.wait_for_selector(
            selector, timeout=self.browser.settings.linkedin_section_timeout_ms
        )

    async def scroll_until_stable(
        self, page: NavigatorPage, *, max_steps: int | None = None, stable_rounds: int | None = None
    ) -> int:
        steps = max_steps or self.browser.settings.linkedin_scroll_max_steps
        stable_target = stable_rounds or self.browser.settings.linkedin_scroll_stable_rounds
        stable = 0
        previous: object = None
        for step in range(steps):
            current = await page.evaluate("document.body.scrollHeight")
            if current == previous:
                stable += 1
                if stable >= stable_target:
                    return step + 1
            else:
                stable = 0
            previous = current
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        return steps

    async def expand_visible_buttons(
        self, page: NavigatorPage, section_selector: str
    ) -> tuple[str, ...]:
        locator = await page.locator(
            f"{section_selector} button[aria-label], {section_selector} button[data-view-name]"
        )
        try:
            count = await locator.count()  # type: ignore[attr-defined]
            for index in range(count):
                await locator.nth(index).click()  # type: ignore[attr-defined]
            return ()
        except (OSError, RuntimeError, AttributeError):
            return ("expand_failed",)

    async def close_obstructive_dialogs(self, page: NavigatorPage) -> None:
        return None
