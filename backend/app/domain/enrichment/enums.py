from enum import StrEnum


class EnrichmentMode(StrEnum):
    FAST = "fast"
    DEEP = "deep"


class EnrichmentSection(StrEnum):
    IDENTITY = "identity"
    ABOUT = "about"
    EXPERIENCE = "experience"
    EDUCATION = "education"
    SKILLS = "skills"
    CERTIFICATIONS = "certifications"
    LANGUAGES = "languages"


class EnrichmentProvider(StrEnum):
    MANUAL = "manual"
    LINKEDIN = "linkedin"
    IMPORTED = "imported"
    DEMO = "demo"


class CandidateEnrichmentStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
    CANCELLED = "cancelled"


class EnrichmentImportMode(StrEnum):
    MERGE = "merge"
    REPLACE_SECTIONS = "replace_sections"
    REPLACE_ALL = "replace_all"


class IdentityUpdateStrategy(StrEnum):
    FILL_EMPTY = "fill_empty"
    OVERWRITE_NON_NULL = "overwrite_non_null"
    KEEP_EXISTING = "keep_existing"
