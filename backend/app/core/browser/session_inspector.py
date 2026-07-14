from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from app.config import Settings
from app.core.browser.exceptions import (
    AuthenticationRequiredError,
    CaptchaDetectedError,
    ChallengeDetectedError,
    InvalidSessionStateError,
    SessionFileMissingError,
)
from app.core.browser.manager import BrowserManager
from app.core.browser.page_guard import sanitize_url
from app.core.browser.session_store import LinkedInSessionStore


class SessionHealthStatus(StrEnum):
    MISSING = "missing"
    INVALID = "invalid"
    VALID_FILE = "valid_file"
    AUTHENTICATED = "authenticated"
    EXPIRED = "expired"
    CHALLENGE = "challenge"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class SessionHealthResult:
    status: SessionHealthStatus
    session_file_exists: bool
    storage_state_valid: bool
    authenticated: bool
    challenge_detected: bool
    checked_at: datetime
    current_url: str | None = None
    message: str = ""
    warnings: tuple[str, ...] = field(default_factory=tuple)


class LinkedInSessionInspector:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.store = LinkedInSessionStore(settings.linkedin_session_file)

    async def inspect(self) -> SessionHealthResult:
        checked_at = datetime.now(UTC)
        if not self.store.exists():
            return SessionHealthResult(
                SessionHealthStatus.MISSING,
                False,
                False,
                False,
                False,
                checked_at,
                message="LinkedIn session file is missing.",
            )
        try:
            self.store.validate_storage_state_file()
        except (InvalidSessionStateError, SessionFileMissingError):
            return SessionHealthResult(
                SessionHealthStatus.INVALID,
                True,
                False,
                False,
                False,
                checked_at,
                message="LinkedIn session file is invalid.",
            )
        manager = BrowserManager(self.settings, session_store=self.store)
        current_url: str | None = None
        try:
            async with manager:
                page = await manager.new_page(require_session=True)
                await manager.navigate(page, f"{self.settings.linkedin_base_url.rstrip('/')}/feed/")
                current_url = sanitize_url(page.url)
                return SessionHealthResult(
                    SessionHealthStatus.AUTHENTICATED,
                    True,
                    True,
                    True,
                    False,
                    checked_at,
                    current_url=current_url,
                    message="LinkedIn session is authenticated.",
                )
        except AuthenticationRequiredError:
            return SessionHealthResult(
                SessionHealthStatus.EXPIRED,
                True,
                True,
                False,
                False,
                checked_at,
                current_url=current_url,
                message="LinkedIn session has expired.",
            )
        except (ChallengeDetectedError, CaptchaDetectedError):
            return SessionHealthResult(
                SessionHealthStatus.CHALLENGE,
                True,
                True,
                False,
                True,
                checked_at,
                current_url=current_url,
                message="LinkedIn requires manual security verification.",
            )
