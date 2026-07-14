from datetime import UTC, datetime, timedelta
from enum import StrEnum
from uuid import uuid4

import pytest

from app.db.enums import CandidateProfileStatus
from app.domain.candidates import CandidateMergeConflictError, CandidateValidationError
from app.domain.candidates.merge import duplicate_suggestion, select_merged_fields
from app.domain.candidates.normalizers import (
    evaluate_candidate_eligibility,
    normalize_candidate_location,
    normalize_candidate_name,
    parse_headline_identity,
)
from app.domain.candidates.quality import CandidateQualityInput, calculate_candidate_quality
from app.domain.candidates.types import (
    CandidateDiscoveryInput,
    CandidateEligibilitySource,
    CandidateFieldStrategy,
)
from app.services.candidates import CandidateService


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("  Demo   Engineer  ", "Demo Engineer"),
        ("Dr. Örnek Çalışan", "Örnek Çalışan"),
        ("Demo Engineer | LinkedIn", "Demo Engineer"),
        ("Demo Engineer adlı kullanıcının profili", "Demo Engineer"),
        ("LinkedIn Member", None),
        ("Unknown", None),
    ],
)
def test_name_normalization(raw: str, expected: str | None) -> None:
    assert normalize_candidate_name(raw) == expected


@pytest.mark.parametrize(
    ("raw", "city", "country"),
    [
        ("Bursa, Türkiye", "Bursa", "Turkey"),
        ("İstanbul, Türkiye", "Istanbul", "Turkey"),
        ("Kocaeli, Turkey", "Kocaeli", "Turkey"),
        ("Türkiye", None, "Turkey"),
        ("Gemlik, Bursa", "Gemlik", None),
        ("Remote - EMEA", None, None),
    ],
)
def test_location_normalization(raw: str, city: str | None, country: str | None) -> None:
    result = normalize_candidate_location(raw)
    assert result.location_raw == raw
    assert result.city == city
    assert result.country == country


def test_headline_identity_is_conservative() -> None:
    exact = parse_headline_identity("Software Engineer at Demo Company | LinkedIn")
    assert (exact.current_title, exact.current_company, exact.confidence) == (
        "Software Engineer",
        "Demo Company",
        0.95,
    )
    skills = parse_headline_identity("Software Engineer | Python | SQL")
    assert skills.current_title == "Software Engineer"
    assert skills.current_company is None
    student = parse_headline_identity("Computer Engineering Student")
    assert student.current_title is None
    assert student.current_company is None


def _input(
    url: str, *, slug: str | None = None, name: str | None = "Demo Engineer"
) -> CandidateDiscoveryInput:
    return CandidateDiscoveryInput(
        search_result_id=uuid4(),
        normalized_url=url,
        source_url=url,
        displayed_name=name,
        candidate_profile_slug=slug,
    )


def test_linkedin_profile_eligibility() -> None:
    result = evaluate_candidate_eligibility(
        _input("https://www.linkedin.com/in/demo-engineer", slug="demo-engineer")
    )
    assert result.eligible is True
    assert result.source_type is CandidateEligibilitySource.LINKEDIN_PROFILE
    assert result.confidence == 0.98


@pytest.mark.parametrize("path", ["company/demo", "jobs/view/1", "school/demo"])
def test_non_person_linkedin_pages_are_skipped(path: str) -> None:
    assert evaluate_candidate_eligibility(_input(f"https://linkedin.com/{path}")).eligible is False


def test_github_profile_requires_metadata() -> None:
    assert evaluate_candidate_eligibility(_input("https://github.com/demo")).confidence == 0.8
    assert (
        evaluate_candidate_eligibility(_input("https://github.com/demo", name=None)).eligible
        is False
    )


def test_quality_empty_and_deterministic() -> None:
    first = calculate_candidate_quality(CandidateQualityInput())
    second = calculate_candidate_quality(CandidateQualityInput())
    assert first == second
    assert first.total_score == 0
    assert len(first.missing_fields) == 11


def test_quality_full_score_and_breakdown() -> None:
    data = CandidateQualityInput(
        full_name="Demo Engineer",
        normalized_profile_url="https://linkedin.com/in/demo-engineer",
        headline="Engineer",
        location_raw="Bursa, Türkiye",
        current_title="Engineer",
        current_company="Demo",
        about="Profile about",
        discovery_snippet="Search snippet",
        experience_count=1,
        education_count=1,
        skill_count=3,
    )
    result = calculate_candidate_quality(data)
    assert result.total_score == 100
    assert not result.missing_fields
    assert sum(result.field_scores.values()) == 100


def test_quality_rejects_placeholder_and_invalid_profile_url() -> None:
    result = calculate_candidate_quality(
        CandidateQualityInput(full_name="Profile", normalized_profile_url="javascript:alert(1)")
    )
    assert result.total_score == 0
    assert result.warnings == ["placeholder_name", "invalid_candidate_profile_url"]


def test_merge_field_strategies() -> None:
    old = datetime.now(UTC) - timedelta(days=1)
    new = datetime.now(UTC)
    target = {"full_name": "Target Name", "headline": None, "updated_at": old}
    source = {"full_name": "Source Name", "headline": "New", "updated_at": new}
    keep, conflicts = select_merged_fields(target, [source], CandidateFieldStrategy.KEEP_TARGET)
    assert keep["full_name"] == "Target Name"
    assert keep["headline"] == "New"
    assert "full_name" in conflicts
    newest, _ = select_merged_fields(target, [source], CandidateFieldStrategy.PREFER_NEWEST)
    assert newest["full_name"] == "Source Name"


def test_duplicate_suggestion_signals() -> None:
    candidate_id = uuid4()
    exact = duplicate_suggestion(
        candidate_id=candidate_id,
        base={"normalized_profile_url": "https://example.com/person"},
        other={"normalized_profile_url": "https://example.com/person"},
    )
    assert exact is not None and exact.score == 1.0
    supported = duplicate_suggestion(
        candidate_id=candidate_id,
        base={"full_name": "Demo Engineer", "headline": "Engineer", "city": "Bursa"},
        other={"full_name": "Demo Engineer", "headline": "Engineer", "city": "Bursa"},
    )
    assert supported is not None and supported.score == 0.95
    name_only = duplicate_suggestion(
        candidate_id=candidate_id,
        base={"full_name": "Demo Engineer"},
        other={"full_name": "Demo Engineer"},
    )
    assert name_only is None


def test_additional_duplicate_signals_and_fuzzy_support() -> None:
    candidate_id = uuid4()
    slug = duplicate_suggestion(
        candidate_id=candidate_id,
        base={"profile_slug": "same-slug"},
        other={"profile_slug": "SAME-SLUG"},
    )
    assert slug is not None and slug.score == 0.99
    company = duplicate_suggestion(
        candidate_id=candidate_id,
        base={"full_name": "Demo Engineer", "current_company": "Demo Company"},
        other={"full_name": "Demo Engineer", "current_company": "demo company"},
    )
    assert company is not None and company.score == 0.9
    fuzzy = duplicate_suggestion(
        candidate_id=candidate_id,
        base={"full_name": "Demo Engineer", "city": "Bursa"},
        other={"full_name": "Demo Enginer", "city": "bursa"},
    )
    assert fuzzy is not None and fuzzy.score < 0.9


def test_merge_explicit_validation_helpers() -> None:
    target = uuid4()
    with pytest.raises(CandidateMergeConflictError):
        CandidateService._validate_merge_ids(target, [])
    with pytest.raises(CandidateMergeConflictError):
        CandidateService._validate_merge_ids(target, [uuid4() for _ in range(21)])
    with pytest.raises(CandidateMergeConflictError):
        CandidateService._prepare_explicit_merge_values({"normalized_profile_url": "protected"})
    with pytest.raises(CandidateMergeConflictError):
        CandidateService._prepare_explicit_merge_values({"profile_status": "invalid"})
    with pytest.raises(CandidateMergeConflictError):
        CandidateService._prepare_explicit_merge_values({"total_experience_months": -1})
    prepared = CandidateService._prepare_explicit_merge_values(
        {
            "profile_status": "queued",
            "total_experience_months": 24,
            "primary_profile_url": "https://linkedin.com/in/explicit-person?trk=test",
        }
    )
    assert prepared["profile_status"] is CandidateProfileStatus.QUEUED
    assert prepared["normalized_profile_url"] == "https://www.linkedin.com/in/explicit-person"


def test_candidate_service_serialization_and_note_helpers() -> None:
    class DemoEnum(StrEnum):
        VALUE = "value"

    identifier = uuid4()
    instant = datetime.now(UTC)
    result = CandidateService._json_values(
        {"enum": DemoEnum.VALUE, "time": instant, "id": identifier, "number": 3}
    )
    assert result == {
        "enum": "value",
        "time": instant.isoformat(),
        "id": str(identifier),
        "number": 3,
    }
    assert CandidateService._join_notes(None, " Source ", "Merged") == "Source"
    assert CandidateService._join_notes("Same", " Same ", "Merged") == "Same"
    assert CandidateService._join_notes("Current", None, "Merged") == "Current"
    assert CandidateService._join_notes("Current", "Source", "Merged") == (
        "Current\n\n[Merged]\nSource"
    )
    assert "profile_url_conflict_requires_identity_review" in CandidateService._merge_warnings(
        ["normalized_profile_url"]
    )


def test_candidate_service_defensive_normalization_branches() -> None:
    with pytest.raises(CandidateValidationError):
        CandidateService._prepare_data({"primary_profile_url": 123})
    cleared = CandidateService._prepare_data(
        {"primary_profile_url": None, "headline": None, "location_raw": None}, partial=True
    )
    assert cleared["normalized_profile_url"] is None
    assert cleared["profile_slug"] is None
    assert cleared["headline"] is None
    assert cleared["location_raw"] is None
    CandidateService._validate_status_transition(
        CandidateProfileStatus.DISCOVERED, CandidateProfileStatus.DISCOVERED
    )
