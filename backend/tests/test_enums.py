from enum import StrEnum

from app.db.enums import (
    BackgroundTaskStatus,
    BackgroundTaskType,
    CandidateProfileStatus,
    CandidateSkillSource,
    CandidateSource,
    JobSource,
    JobStatus,
    RequirementImportance,
    RequirementSource,
    RequirementType,
    SearchLanguage,
    SearchSource,
    SearchStatus,
    ShortlistStatus,
)


def values(enum_type: type[StrEnum]) -> set[str]:
    return {member.value for member in enum_type}


def test_domain_enum_values() -> None:
    assert values(JobSource) == {"manual", "kariyer_net", "linkedin", "other"}
    assert values(JobStatus) == {"draft", "parsed", "sourcing", "completed", "archived"}
    assert values(RequirementType) == {
        "title",
        "skill",
        "education",
        "experience",
        "location",
        "language",
        "certification",
        "industry",
    }
    assert values(RequirementImportance) == {"required", "preferred", "optional"}
    assert values(RequirementSource) == {"rule", "ai", "manual"}
    assert values(SearchSource) == {"google_xray", "manual", "professional_network"}
    assert values(SearchLanguage) == {"tr", "en"}
    assert values(SearchStatus) == {"draft", "ready", "running", "completed", "failed"}
    assert values(CandidateSource) == {
        "google_xray",
        "professional_network",
        "manual",
        "imported",
        "demo",
    }
    assert values(CandidateProfileStatus) == {
        "discovered",
        "queued",
        "scraped",
        "partial",
        "unavailable",
        "failed",
    }
    assert values(CandidateSkillSource) == {
        "profile_skill",
        "experience_text",
        "about_text",
        "inferred",
        "manual",
    }
    assert values(ShortlistStatus) == {"shortlisted", "reviewed", "rejected", "contacted"}
    assert values(BackgroundTaskType) == {
        "parse_job",
        "generate_queries",
        "execute_search",
        "import_search_results",
        "scrape_profile_fast",
        "scrape_profile_deep",
        "match_candidate",
        "match_all_candidates",
    }
    assert values(BackgroundTaskStatus) == {
        "pending",
        "running",
        "completed",
        "failed",
        "cancelled",
    }
