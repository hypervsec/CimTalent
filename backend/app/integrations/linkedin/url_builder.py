from app.domain.linkedin.exceptions import LinkedInProfileUrlInvalidError
from app.sourcing.profile_url_normalizer import normalize_url


class LinkedInProfileUrlBuilder:
    def canonical_profile_url(self, value: str) -> str:
        normalized = normalize_url(value)
        if (
            normalized is None
            or normalized.source_domain != "linkedin.com"
            or not normalized.candidate_profile_slug
        ):
            raise LinkedInProfileUrlInvalidError("A LinkedIn person profile URL is required.")
        return normalized.value

    def detail_url(self, value: str, section: str) -> str:
        base = self.canonical_profile_url(value)
        allowed = {"experience", "education", "skills", "certifications", "languages"}
        if section not in allowed:
            raise LinkedInProfileUrlInvalidError("Unsupported LinkedIn profile section.")
        return f"{base}/details/{section}/"
