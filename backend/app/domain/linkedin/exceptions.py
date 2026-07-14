class LinkedInDomainError(Exception):
    code = "linkedin_error"

    def __init__(self, message: str, **details: object) -> None:
        super().__init__(message)
        self.message = message
        self.details = details


class LinkedInProfileUrlInvalidError(LinkedInDomainError):
    code = "linkedin_profile_url_invalid"


class LinkedInProviderDisabledError(LinkedInDomainError):
    code = "linkedin_provider_disabled"


class LinkedInParsingError(LinkedInDomainError):
    code = "linkedin_parsing_error"


class SelectorChangedError(LinkedInParsingError):
    code = "linkedin_selector_changed"
