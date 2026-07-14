from datetime import UTC, date, datetime
from uuid import uuid4

import pytest

from app.db.enums import CandidateSkillSource
from app.domain.enrichment.enums import EnrichmentMode, EnrichmentProvider, EnrichmentSection
from app.domain.enrichment.exceptions import (
    CandidateEnrichmentStateError,
    CandidateEnrichmentValidationError,
)
from app.domain.enrichment.normalizers import (
    experience_fingerprint,
    normalize_certification,
    normalize_education,
    normalize_experience,
    normalize_language,
    normalize_skill,
    total_experience_months,
)
from app.domain.enrichment.types import (
    CandidateEnrichmentRequest,
    CandidateEnrichmentResult,
    EnrichedCertification,
    EnrichedEducation,
    EnrichedExperience,
    EnrichedLanguage,
    EnrichedSkill,
)
from app.enrichment.manual_provider import ManualEnrichmentProvider
from app.enrichment.orchestrator import CandidateEnrichmentOrchestrator


def test_experience_normalization_is_deterministic() -> None:
    raw = EnrichedExperience(
        "  Yazılım   Mühendisi ",
        company_name=" Demo  Company ",
        company_url="HTTPS://EXAMPLE.COM/jobs/?utm_source=test",
        start_date=date(2020, 1, 15),
        end_date=date(2022, 12, 2),
        duration_months=999,
        skills_detected=("MS SQL", "SQL Server", " RESTful API "),
        external_key=" PROFILE-1 ",
    )
    result = normalize_experience(raw)
    assert result.position_title_normalized == "software engineer"
    assert result.company_name == "Demo Company"
    assert result.company_url == "https://example.com/jobs"
    assert result.duration_months == 36
    assert result.skills_detected == ("sql server", "rest api")
    assert result.external_key == "profile-1"
    assert experience_fingerprint(result) == experience_fingerprint(normalize_experience(raw))


def test_current_experience_uses_explicit_today() -> None:
    result = normalize_experience(
        EnrichedExperience("Backend Developer", start_date=date(2024, 1, 1), is_current=True),
        today=date(2024, 3, 31),
    )
    assert result.duration_months == 3
    with pytest.raises(CandidateEnrichmentValidationError):
        normalize_experience(
            EnrichedExperience(
                "Backend Developer",
                start_date=date(2024, 1, 1),
                end_date=date(2024, 2, 1),
                is_current=True,
            )
        )


def test_invalid_experience_date_range_is_rejected() -> None:
    with pytest.raises(CandidateEnrichmentValidationError):
        normalize_experience(
            EnrichedExperience("Engineer", start_date=date(2024, 2, 1), end_date=date(2024, 1, 1))
        )


def test_education_skill_certification_and_language_taxonomies_are_reused() -> None:
    education = normalize_education(
        EnrichedEducation(
            "  Demo University ", field_of_study="Bilgisayar Mühendisliği", start_year=2018
        )
    )
    assert education.field_of_study_normalized == "computer engineering"

    skill = normalize_skill(
        EnrichedSkill(
            "RESTful API",
            "ignored",
            source=CandidateSkillSource.INFERRED,
            confidence=0.9,
        )
    )
    assert (skill.normalized_name, skill.category, skill.confidence) == (
        "rest api",
        "framework",
        0.5,
    )

    certification = normalize_certification(
        EnrichedCertification("NDT Level II", credential_url="https://example.com/c/1")
    )
    assert certification.name == "ndt level 2"

    language = normalize_language(EnrichedLanguage("Türkçe", "ignored", proficiency="Ana dil"))
    assert (language.language_normalized, language.proficiency) == ("turkish", "native")


@pytest.mark.parametrize(
    "item",
    [
        EnrichedEducation("University", start_year=1899),
        EnrichedEducation("University", start_year=2020, end_year=2019),
    ],
)
def test_invalid_education_years_are_rejected(item: EnrichedEducation) -> None:
    with pytest.raises(CandidateEnrichmentValidationError):
        normalize_education(item)


def test_invalid_skill_and_certification_are_rejected() -> None:
    with pytest.raises(CandidateEnrichmentValidationError):
        normalize_skill(EnrichedSkill("Python", "python", endorsement_count=-1))
    with pytest.raises(CandidateEnrichmentValidationError):
        normalize_certification(
            EnrichedCertification(
                "Certificate", issue_date=date(2024, 2, 1), expiration_date=date(2024, 1, 1)
            )
        )
    with pytest.raises(CandidateEnrichmentValidationError):
        normalize_certification(
            EnrichedCertification("Certificate", credential_url="javascript:alert(1)")
        )


def test_timeline_merges_overlaps_and_deduplicates() -> None:
    experiences = [
        EnrichedExperience(
            "Engineer", company_name="A", start_date=date(2020, 1, 1), end_date=date(2022, 12, 1)
        ),
        EnrichedExperience(
            "Lead", company_name="B", start_date=date(2021, 6, 1), end_date=date(2023, 6, 1)
        ),
        EnrichedExperience(
            "Lead", company_name="B", start_date=date(2021, 6, 1), end_date=date(2023, 6, 1)
        ),
        EnrichedExperience("Unknown", duration_months=4),
    ]
    assert total_experience_months(experiences, today=date(2024, 1, 1)) == 46
    assert total_experience_months(tuple(reversed(experiences)), today=date(2024, 1, 1)) == 46


def test_timeline_handles_current_adjacent_and_missing_dates() -> None:
    experiences = [
        EnrichedExperience("A", start_date=date(2023, 11, 1), end_date=date(2023, 12, 31)),
        EnrichedExperience("B", start_date=date(2024, 1, 1), is_current=True),
        EnrichedExperience("Ignored", start_date=date(2020, 1, 1)),
    ]
    assert total_experience_months(experiences, today=date(2024, 2, 29)) == 4


async def test_manual_provider_runs_through_platform_independent_orchestrator() -> None:
    now = datetime.now(UTC)
    result = CandidateEnrichmentResult(
        EnrichmentProvider.MANUAL,
        EnrichmentMode.FAST,
        now,
        now,
    )
    request = CandidateEnrichmentRequest(
        uuid4(),
        None,
        EnrichmentMode.FAST,
        (EnrichmentSection.IDENTITY,),
    )
    orchestrator = CandidateEnrichmentOrchestrator(ManualEnrichmentProvider(result))
    assert await orchestrator.run(request) is result
    incompatible = CandidateEnrichmentRequest(
        request.candidate_id,
        None,
        EnrichmentMode.DEEP,
        (),
    )
    with pytest.raises(CandidateEnrichmentStateError):
        await orchestrator.run(incompatible)
