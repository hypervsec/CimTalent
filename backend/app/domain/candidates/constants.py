from types import MappingProxyType

QUALITY_WEIGHTS = MappingProxyType(
    {
        "full_name": 15,
        "normalized_profile_url": 15,
        "headline": 10,
        "location": 10,
        "current_title": 10,
        "current_company": 10,
        "about": 5,
        "discovery_snippet": 5,
        "experience": 10,
        "education": 5,
        "skills": 5,
    }
)

PLACEHOLDER_NAMES = frozenset(
    {
        "linkedin",
        "profile",
        "user",
        "member",
        "linkedin member",
        "test",
        "unknown",
        "n/a",
    }
)

LINKEDIN_BLOCKED_PATHS = ("/company/", "/jobs/", "/school/", "/search/", "/feed/")
SEARCH_ENGINE_DOMAINS = frozenset(
    {"google.com", "www.google.com", "bing.com", "www.bing.com", "yahoo.com"}
)
