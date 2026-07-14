class BrowserInfrastructureError(Exception):
    """Base error that never contains cookies or storage-state content."""


class BrowserInitializationError(BrowserInfrastructureError):
    pass


class BrowserNotStartedError(BrowserInfrastructureError):
    pass


class SessionFileMissingError(BrowserInfrastructureError):
    pass


class InvalidSessionStateError(BrowserInfrastructureError):
    pass


class SessionExpiredError(BrowserInfrastructureError):
    pass


class AuthenticationRequiredError(BrowserInfrastructureError):
    pass


class ChallengeDetectedError(BrowserInfrastructureError):
    pass


class CaptchaDetectedError(BrowserInfrastructureError):
    pass


class RateLimitDetectedError(BrowserInfrastructureError):
    pass


class AccessDeniedError(BrowserInfrastructureError):
    pass


class PageNavigationError(BrowserInfrastructureError):
    pass


class PageNavigationTimeoutError(PageNavigationError):
    pass


class BrowserArtifactError(BrowserInfrastructureError):
    pass


class ProfileUnavailableError(BrowserInfrastructureError):
    pass


class SelectorChangedError(BrowserInfrastructureError):
    pass
