from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol
from urllib.parse import urlsplit, urlunsplit

from app.core.browser.exceptions import (
    AccessDeniedError,
    AuthenticationRequiredError,
    CaptchaDetectedError,
    ChallengeDetectedError,
    ProfileUnavailableError,
    RateLimitDetectedError,
)


class GuardPage(Protocol):
    @property
    def url(self) -> str: ...
    async def content(self) -> str: ...


class PageState(StrEnum):
    AUTHENTICATED = "authenticated"
    LOGIN = "login"
    CHALLENGE = "challenge"
    RATE_LIMIT = "rate_limit"
    ACCESS_DENIED = "access_denied"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class PageGuardResult:
    state: PageState
    sanitized_url: str


class LinkedInPageGuard:
    LOGIN_PATHS = ("/login", "/uas/login", "/authwall")
    CHALLENGE_PATHS = ("/checkpoint", "/challenge")
    CHALLENGE_TEXT = (
        "verify your identity",
        "security verification",
        "let's do a quick security check",
        "kimliğinizi doğrulayın",
        "güvenlik doğrulaması",
    )
    RATE_LIMIT_TEXT = (
        "too many requests",
        "commercial use limit",
        "çok fazla istek",
    )
    UNAVAILABLE_TEXT = (
        "this profile is not available",
        "page not found",
        "bu profil kullanılamıyor",
        "sayfa bulunamadı",
    )

    async def inspect(self, page: GuardPage) -> PageGuardResult:
        sanitized = sanitize_url(page.url)
        path = urlsplit(page.url).path.casefold()
        if any(pattern in path for pattern in self.LOGIN_PATHS):
            raise AuthenticationRequiredError("LinkedIn authentication is required.")
        if any(pattern in path for pattern in self.CHALLENGE_PATHS):
            raise ChallengeDetectedError("LinkedIn security challenge was detected.")
        content = (await page.content()).casefold()
        if "captcha" in content:
            raise CaptchaDetectedError("LinkedIn CAPTCHA was detected.")
        if any(pattern in content for pattern in self.CHALLENGE_TEXT):
            raise ChallengeDetectedError("LinkedIn security challenge was detected.")
        if any(pattern in content for pattern in self.RATE_LIMIT_TEXT):
            raise RateLimitDetectedError("LinkedIn rate limit was detected.")
        if "access denied" in content or "erişim reddedildi" in content:
            raise AccessDeniedError("LinkedIn access was denied.")
        if any(pattern in content for pattern in self.UNAVAILABLE_TEXT):
            raise ProfileUnavailableError("LinkedIn profile is unavailable.")
        if urlsplit(page.url).hostname and str(urlsplit(page.url).hostname).endswith(
            "linkedin.com"
        ):
            return PageGuardResult(PageState.AUTHENTICATED, sanitized)
        return PageGuardResult(PageState.UNKNOWN, sanitized)


def sanitize_url(value: str) -> str:
    parts = urlsplit(value)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
