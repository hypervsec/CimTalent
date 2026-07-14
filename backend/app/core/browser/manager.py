from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from importlib import import_module
from typing import Any, Protocol, cast

from app.config import Settings
from app.core.browser.artifacts import ArtifactPage, BrowserArtifactManager
from app.core.browser.exceptions import (
    BrowserInitializationError,
    BrowserNotStartedError,
    InvalidSessionStateError,
    PageNavigationError,
    PageNavigationTimeoutError,
    SessionFileMissingError,
)
from app.core.browser.page_guard import GuardPage, LinkedInPageGuard
from app.core.browser.session_store import LinkedInSessionStore


class Page(GuardPage, ArtifactPage, Protocol):
    def set_default_timeout(self, timeout: float) -> None: ...
    def set_default_navigation_timeout(self, timeout: float) -> None: ...
    async def goto(self, url: str, **kwargs: object) -> object: ...
    async def close(self) -> None: ...


class BrowserContext(Protocol):
    async def new_page(self) -> Page: ...
    async def close(self) -> None: ...
    async def storage_state(self) -> dict[str, object]: ...


class Browser(Protocol):
    async def new_context(self, **kwargs: object) -> BrowserContext: ...
    async def close(self) -> None: ...


class PlaywrightRuntime(Protocol):
    @property
    def chromium(self) -> Any: ...
    async def stop(self) -> None: ...


class BrowserManager:
    def __init__(
        self,
        settings: Settings,
        *,
        session_store: LinkedInSessionStore | None = None,
        page_guard: LinkedInPageGuard | None = None,
        artifact_manager: BrowserArtifactManager | None = None,
        runtime_factory: object | None = None,
    ) -> None:
        self.settings = settings
        self.session_store = session_store or LinkedInSessionStore(settings.linkedin_session_file)
        self.page_guard = page_guard or LinkedInPageGuard()
        self.artifacts = artifact_manager or BrowserArtifactManager(
            settings.browser_artifact_dir,
            save_screenshot=settings.browser_save_screenshot_on_error,
            save_html=settings.browser_save_html_on_error,
        )
        self._runtime_factory = runtime_factory
        self._runtime: PlaywrightRuntime | None = None
        self._browser: Browser | None = None
        self._contexts: list[BrowserContext] = []

    @property
    def started(self) -> bool:
        return self._browser is not None

    async def __aenter__(self) -> BrowserManager:
        await self.start()
        return self

    async def __aexit__(self, exc_type: object, exc: object, traceback: object) -> None:
        await self.close()

    async def start(self) -> None:
        if self.started:
            raise BrowserInitializationError("BrowserManager is already started.")
        try:
            factory = self._runtime_factory
            if factory is None:
                factory = import_module("playwright.async_api").async_playwright()
            runtime = await cast(Any, factory).start()
            browser = await runtime.chromium.launch(
                headless=self.settings.browser_headless,
                slow_mo=self.settings.browser_slow_mo_ms,
            )
        except (ImportError, OSError, RuntimeError) as exc:
            raise BrowserInitializationError(
                "Playwright is unavailable or Chromium could not be started."
            ) from exc
        self._runtime = cast(PlaywrightRuntime, runtime)
        self._browser = cast(Browser, browser)

    async def new_page(self, *, require_session: bool = False) -> Page:
        if self._browser is None:
            raise BrowserNotStartedError("BrowserManager has not been started.")
        state: Mapping[str, object] | None = None
        if self.session_store.exists():
            state = self.session_store.load_storage_state()
        elif require_session:
            raise SessionFileMissingError("A LinkedIn session is required.")
        options: dict[str, object] = {
            "viewport": {
                "width": self.settings.browser_viewport_width,
                "height": self.settings.browser_viewport_height,
            }
        }
        if state is not None:
            options["storage_state"] = state
        if self.settings.browser_user_agent:
            options["user_agent"] = self.settings.browser_user_agent
        try:
            context = await self._browser.new_context(**options)
            page = await context.new_page()
        except (OSError, RuntimeError, InvalidSessionStateError) as exc:
            raise BrowserInitializationError("Browser context could not be created.") from exc
        page.set_default_timeout(self.settings.browser_timeout_ms)
        page.set_default_navigation_timeout(self.settings.browser_navigation_timeout_ms)
        self._contexts.append(context)
        return page

    async def navigate(self, page: Page, url: str) -> None:
        try:
            await page.goto(url, wait_until="domcontentloaded")
        except TimeoutError as exc:
            raise PageNavigationTimeoutError("Browser navigation timed out.") from exc
        except (OSError, RuntimeError) as exc:
            raise PageNavigationError("Browser navigation failed.") from exc
        await self.page_guard.inspect(page)

    async def storage_state(self) -> dict[str, object]:
        if not self._contexts:
            raise BrowserNotStartedError("No browser context is available.")
        return await self._contexts[-1].storage_state()

    @asynccontextmanager
    async def session_page(
        self, *, require_session: bool = True, correlation_id: str | None = None
    ) -> AsyncIterator[Page]:
        page = await self.new_page(require_session=require_session)
        try:
            yield page
        except (OSError, RuntimeError, ValueError) as exc:
            if (
                self.settings.browser_save_screenshot_on_error
                or self.settings.browser_save_html_on_error
            ):
                await self.artifacts.capture(
                    page,
                    event="browser_error",
                    correlation_id=correlation_id,
                    exception=exc,
                )
            raise
        finally:
            await page.close()

    async def close(self) -> None:
        for context in reversed(self._contexts):
            try:
                await context.close()
            except (OSError, RuntimeError):
                pass
        self._contexts.clear()
        if self._browser is not None:
            try:
                await self._browser.close()
            except (OSError, RuntimeError):
                pass
        if self._runtime is not None:
            try:
                await self._runtime.stop()
            except (OSError, RuntimeError):
                pass
        self._browser = None
        self._runtime = None
