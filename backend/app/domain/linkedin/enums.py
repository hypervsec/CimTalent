from enum import StrEnum


class LinkedInProviderMode(StrEnum):
    LIVE = "live"
    FIXTURE = "fixture"


class LinkedInPageKind(StrEnum):
    PROFILE = "profile"
    EXPERIENCE = "experience"
    EDUCATION = "education"
    SKILLS = "skills"
    CERTIFICATIONS = "certifications"
    LANGUAGES = "languages"
