from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast

import pytest

from app.config import Settings
from app.core.browser.artifacts import BrowserArtifactManager
from app.core.browser.exceptions import (
    AuthenticationRequiredError,
    CaptchaDetectedError,
    ChallengeDetectedError,
    InvalidSessionStateError,
    RateLimitDetectedError,
    SessionFileMissingError,
)
from app.core.browser.manager import BrowserManager
from app.core.browser.page_guard import LinkedInPageGuard, PageState, sanitize_url
from app.core.browser.session_inspector import LinkedInSessionInspector, SessionHealthStatus
from app.core.browser.session_store import LinkedInSessionStore
from app.core.browser.settings import Settings as BrowserSettings


class FakePage:
    def __init__(self, url: str = "https://www.linkedin.com/feed/", html: str = "ok") -> None:
        self._url = url
        self.html = html
        self.timeout = 0
        self.navigation_timeout = 0
        self.closed = False

    @property
    def url(self) -> str:
        return self._url

    async def content(self) -> str:
        return self.html

    async def screenshot(self, *, path: str, full_page: bool) -> None:
        return None

    def set_default_timeout(self, timeout: float) -> None:
        self.timeout = int(timeout)

    def set_default_navigation_timeout(self, timeout: float) -> None:
        self.navigation_timeout = int(timeout)

    async def goto(self, url: str, **kwargs: object) -> object:
        self._url = url
        return None

    async def close(self) -> None:
        self.closed = True


class FakeContext:
    def __init__(self) -> None:
        self.page = FakePage()
        self.closed = False

    async def new_page(self) -> FakePage:
        return self.page

    async def close(self) -> None:
        self.closed = True

    async def storage_state(self) -> dict[str, object]:
        return {"cookies": [], "origins": []}


class FakeBrowser:
    def __init__(self) -> None:
        self.context = FakeContext()
        self.options: dict[str, object] = {}
        self.closed = False

    async def new_context(self, **kwargs: object) -> FakeContext:
        self.options = kwargs
        return self.context

    async def close(self) -> None:
        self.closed = True


class FakeChromium:
    def __init__(self, browser: FakeBrowser) -> None:
        self.browser = browser

    async def launch(self, **kwargs: object) -> FakeBrowser:
        return self.browser


class FakeRuntime:
    def __init__(self, browser: FakeBrowser) -> None:
        self.chromium = FakeChromium(browser)
        self.stopped = False

    async def stop(self) -> None:
        self.stopped = True


class FakeFactory:
    def __init__(self, runtime: FakeRuntime) -> None:
        self.runtime = runtime

    async def start(self) -> FakeRuntime:
        return self.runtime


def storage_state() -> dict[str, object]:
    return {
        "cookies": [{"name": "li_at", "value": "secret", "domain": ".linkedin.com"}],
        "origins": [],
    }


def test_session_store_atomic_round_trip_and_safe_metadata(tmp_path: Path) -> None:
    path = tmp_path / "linkedin.json"
    store = LinkedInSessionStore(path)
    assert store.exists() is False
    with pytest.raises(SessionFileMissingError):
        store.load_storage_state()
    store.save_storage_state(storage_state())
    assert store.load_storage_state() == storage_state()
    metadata = store.metadata()
    assert metadata.valid and metadata.has_linkedin_cookie
    assert "secret" not in repr(metadata)
    store.save_storage_state({"cookies": [], "origins": []})
    assert store.load_storage_state()["cookies"] == []
    store.delete_storage_state()
    assert not store.exists()


def test_session_store_rejects_invalid_unsafe_and_large_files(tmp_path: Path) -> None:
    invalid = tmp_path / "invalid.json"
    invalid.write_text("not-json", encoding="utf-8")
    with pytest.raises(InvalidSessionStateError):
        LinkedInSessionStore(invalid).load_storage_state()
    missing_cookies = tmp_path / "missing.json"
    missing_cookies.write_text(json.dumps({"origins": []}), encoding="utf-8")
    with pytest.raises(InvalidSessionStateError):
        LinkedInSessionStore(missing_cookies).load_storage_state()
    large = tmp_path / "large.json"
    large.write_text(json.dumps(storage_state()), encoding="utf-8")
    with pytest.raises(InvalidSessionStateError):
        LinkedInSessionStore(large, max_bytes=2).load_storage_state()
    with pytest.raises(InvalidSessionStateError):
        LinkedInSessionStore(Path("../outside.json"))


@pytest.mark.parametrize(
    ("url", "html", "error"),
    [
        ("https://linkedin.com/login", "", AuthenticationRequiredError),
        ("https://linkedin.com/checkpoint/x", "", ChallengeDetectedError),
        ("https://linkedin.com/feed", "CAPTCHA", CaptchaDetectedError),
        ("https://linkedin.com/feed", "Too many requests", RateLimitDetectedError),
        ("https://linkedin.com/feed", "Güvenlik doğrulaması", ChallengeDetectedError),
        ("https://linkedin.com/feed", "Çok fazla istek", RateLimitDetectedError),
    ],
)
async def test_page_guard_stops_on_auth_challenge_and_limits(
    url: str, html: str, error: type[Exception]
) -> None:
    with pytest.raises(error):
        await LinkedInPageGuard().inspect(FakePage(url, html))


async def test_page_guard_accepts_authenticated_page_and_sanitizes_url() -> None:
    result = await LinkedInPageGuard().inspect(
        FakePage("https://www.linkedin.com/feed/?token=secret", "Welcome")
    )
    assert result.state is PageState.AUTHENTICATED
    assert result.sanitized_url == "https://www.linkedin.com/feed/"
    assert sanitize_url("https://example.com/x?a=secret#fragment") == "https://example.com/x"


async def test_browser_manager_lifecycle_session_and_timeouts(tmp_path: Path) -> None:
    session_path = tmp_path / "session.json"
    store = LinkedInSessionStore(session_path)
    store.save_storage_state(storage_state())
    browser = FakeBrowser()
    runtime = FakeRuntime(browser)
    settings = Settings(
        _env_file=None,
        app_env="test",
        linkedin_session_file=session_path,
        browser_artifact_dir=tmp_path / "artifacts",
    )
    manager = BrowserManager(settings, session_store=store, runtime_factory=FakeFactory(runtime))
    await manager.start()
    with pytest.raises(Exception, match="already started"):
        await manager.start()
    page = await manager.new_page(require_session=True)
    fake_page = cast(FakePage, page)
    assert fake_page.timeout == settings.browser_timeout_ms
    assert fake_page.navigation_timeout == settings.browser_navigation_timeout_ms
    assert "storage_state" in browser.options
    await manager.close()
    await manager.close()
    assert browser.closed and runtime.stopped


async def test_browser_manager_requires_session_and_closes_page_on_error(tmp_path: Path) -> None:
    browser = FakeBrowser()
    runtime = FakeRuntime(browser)
    settings = Settings(
        _env_file=None,
        app_env="test",
        linkedin_session_file=tmp_path / "missing.json",
        browser_artifact_dir=tmp_path / "artifacts",
        browser_save_screenshot_on_error=False,
        browser_save_html_on_error=False,
    )
    manager = BrowserManager(settings, runtime_factory=FakeFactory(runtime))
    await manager.start()
    with pytest.raises(SessionFileMissingError):
        await manager.new_page(require_session=True)
    with pytest.raises(RuntimeError):
        async with manager.session_page(require_session=False):
            raise RuntimeError("test failure")
    assert browser.context.page.closed
    await manager.close()


async def test_browser_manager_context_navigation_state_and_artifact(tmp_path: Path) -> None:
    browser = FakeBrowser()
    runtime = FakeRuntime(browser)
    settings = Settings(
        _env_file=None,
        app_env="test",
        linkedin_session_file=tmp_path / "missing.json",
        browser_artifact_dir=tmp_path / "artifacts",
        browser_user_agent="test-agent",
        browser_save_screenshot_on_error=True,
    )
    manager = BrowserManager(settings, runtime_factory=FakeFactory(runtime))
    async with manager:
        page = await manager.new_page()
        await manager.navigate(page, "https://www.linkedin.com/feed/?secret=x")
        assert (await manager.storage_state())["cookies"] == []
        assert browser.options["user_agent"] == "test-agent"
        with pytest.raises(RuntimeError):
            async with manager.session_page(require_session=False, correlation_id="request/1"):
                raise RuntimeError("capture")
    assert any((tmp_path / "artifacts").glob("*.json"))
    assert BrowserSettings is Settings


async def test_artifact_capture_sanitizes_metadata_and_cleanup(tmp_path: Path) -> None:
    directory = tmp_path / "artifacts"
    manager = BrowserArtifactManager(directory, save_screenshot=False, save_html=True)
    page = FakePage("https://www.linkedin.com/in/demo?token=secret", "<main>profile</main>")
    created = await manager.capture(
        page,
        event="navigation/error",
        correlation_id="request/../one",
        exception=RuntimeError("do not persist this message"),
    )
    assert len(created) == 2
    metadata = json.loads(next(path for path in created if path.suffix == ".json").read_text())
    assert metadata["sanitized_url"] == "https://www.linkedin.com/in/demo"
    assert "secret" not in json.dumps(metadata)
    assert "do not persist" not in json.dumps(metadata)
    old = datetime.now(UTC) - timedelta(days=10)
    for path in created:
        os.utime(path, (old.timestamp(), old.timestamp()))
    assert manager.cleanup(3) == 2
    assert manager.cleanup(3) == 0
    assert (
        BrowserArtifactManager(tmp_path / "missing", save_screenshot=True, save_html=False).cleanup(
            3
        )
        == 0
    )
    screenshot_manager = BrowserArtifactManager(
        tmp_path / "screenshots", save_screenshot=True, save_html=False
    )
    screenshot_paths = await screenshot_manager.capture(
        page,
        event="error",
        correlation_id=None,
        exception=RuntimeError("capture"),
    )
    assert {path.suffix for path in screenshot_paths} == {".png", ".json"}


class InspectorManager:
    outcome: type[Exception] | None = None

    def __init__(self, settings: Settings, *, session_store: LinkedInSessionStore) -> None:
        self.page = FakePage()

    async def __aenter__(self) -> InspectorManager:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def new_page(self, *, require_session: bool) -> FakePage:
        return self.page

    async def navigate(self, page: FakePage, url: str) -> None:
        if self.outcome is not None:
            raise self.outcome("inspector signal")
        page._url = url


async def test_session_inspector_missing_invalid_and_browser_outcomes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    session_path = tmp_path / "linkedin.json"
    settings = Settings(
        _env_file=None,
        app_env="test",
        linkedin_session_file=session_path,
        browser_artifact_dir=tmp_path / "artifacts",
    )
    inspector = LinkedInSessionInspector(settings)
    assert (await inspector.inspect()).status is SessionHealthStatus.MISSING
    session_path.write_text("invalid", encoding="utf-8")
    assert (await inspector.inspect()).status is SessionHealthStatus.INVALID
    LinkedInSessionStore(session_path).save_storage_state(storage_state())
    monkeypatch.setattr("app.core.browser.session_inspector.BrowserManager", InspectorManager)

    InspectorManager.outcome = None
    assert (await inspector.inspect()).status is SessionHealthStatus.AUTHENTICATED
    InspectorManager.outcome = AuthenticationRequiredError
    assert (await inspector.inspect()).status is SessionHealthStatus.EXPIRED
    InspectorManager.outcome = ChallengeDetectedError
    challenged = await inspector.inspect()
    assert challenged.status is SessionHealthStatus.CHALLENGE
    assert challenged.challenge_detected
