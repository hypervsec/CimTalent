from enum import StrEnum


class JobSource(StrEnum):
    MANUAL = "manual"
    KARIYER_NET = "kariyer_net"
    LINKEDIN = "linkedin"
    OTHER = "other"


class JobStatus(StrEnum):
    DRAFT = "draft"
    PARSED = "parsed"
    SOURCING = "sourcing"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class RequirementType(StrEnum):
    TITLE = "title"
    SKILL = "skill"
    EDUCATION = "education"
    EXPERIENCE = "experience"
    LOCATION = "location"
    LANGUAGE = "language"
    CERTIFICATION = "certification"
    INDUSTRY = "industry"


class RequirementImportance(StrEnum):
    REQUIRED = "required"
    PREFERRED = "preferred"
    OPTIONAL = "optional"


class RequirementSource(StrEnum):
    RULE = "rule"
    AI = "ai"
    MANUAL = "manual"


class SearchSource(StrEnum):
    GOOGLE_XRAY = "google_xray"
    MANUAL = "manual"
    PROFESSIONAL_NETWORK = "professional_network"


class SearchLanguage(StrEnum):
    TR = "tr"
    EN = "en"


class SearchStatus(StrEnum):
    DRAFT = "draft"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class CandidateSource(StrEnum):
    GOOGLE_XRAY = "google_xray"
    PROFESSIONAL_NETWORK = "professional_network"
    MANUAL = "manual"
    IMPORTED = "imported"
    DEMO = "demo"


class CandidateProfileStatus(StrEnum):
    DISCOVERED = "discovered"
    QUEUED = "queued"
    SCRAPED = "scraped"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"
    FAILED = "failed"


class CandidateSkillSource(StrEnum):
    PROFILE_SKILL = "profile_skill"
    EXPERIENCE_TEXT = "experience_text"
    ABOUT_TEXT = "about_text"
    INFERRED = "inferred"
    MANUAL = "manual"


class ShortlistStatus(StrEnum):
    SHORTLISTED = "shortlisted"
    REVIEWED = "reviewed"
    REJECTED = "rejected"
    CONTACTED = "contacted"


class BackgroundTaskType(StrEnum):
    PARSE_JOB = "parse_job"
    GENERATE_QUERIES = "generate_queries"
    EXECUTE_SEARCH = "execute_search"
    IMPORT_SEARCH_RESULTS = "import_search_results"
    SCRAPE_PROFILE_FAST = "scrape_profile_fast"
    SCRAPE_PROFILE_DEEP = "scrape_profile_deep"
    MATCH_CANDIDATE = "match_candidate"
    MATCH_ALL_CANDIDATES = "match_all_candidates"


class BackgroundTaskStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
