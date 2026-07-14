from pathlib import Path

import pytest

from app.db.enums import RequirementImportance, RequirementType
from app.domain.jobs.parser_exceptions import EmptyJobDescriptionError
from app.domain.jobs.parser_types import JobParseInput
from app.parsers.jobs.orchestrator import deduplicate_requirements
from app.parsers.jobs.rule_based import RuleBasedJobParser

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "jobs"


def fixture_text(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("fixture_name", "title", "expected"),
    [
        ("software_developer_tr.txt", "Yazılım Geliştirme Uzmanı", "python"),
        ("software_developer_en.txt", "Backend Developer", "rest api"),
        ("welding_engineer_tr.txt", "Kaynak Mühendisi", "welded manufacturing"),
        ("planning_engineer_tr.txt", "Planlama Mühendisi", "production planning"),
        ("mixed_language_job.txt", "Software Engineer", "sql server"),
    ],
)
def test_parser_extracts_fixture_skill(fixture_name: str, title: str, expected: str) -> None:
    parsed = RuleBasedJobParser().parse(
        JobParseInput(title=title, description_raw=fixture_text(fixture_name))
    )

    assert expected in {
        item.normalized_value for item in parsed.requirements if item.type is RequirementType.SKILL
    }
    assert parsed.requirements[0].type is RequirementType.TITLE
    assert 0 <= parsed.confidence <= 1


def test_parser_is_deterministic() -> None:
    parser = RuleBasedJobParser()
    data = JobParseInput(
        title="Yazılım Geliştirme Uzmanı",
        description_raw=fixture_text("software_developer_tr.txt"),
        city="Bursa",
        country="Türkiye",
    )

    assert parser.parse(data) == parser.parse(data)


def test_required_duplicate_wins_over_preferred() -> None:
    parsed = RuleBasedJobParser().parse(
        JobParseInput(
            title="Backend Developer",
            description_raw=fixture_text("duplicate_skills_job.txt"),
        )
    )
    python_requirements = [
        item
        for item in parsed.requirements
        if item.type is RequirementType.SKILL and item.normalized_value == "python"
    ]

    assert len(python_requirements) == 1
    assert python_requirements[0].importance is RequirementImportance.REQUIRED
    assert "python" in parsed.required_skills
    assert "python" not in parsed.preferred_skills


def test_minimal_job_returns_title_and_warnings() -> None:
    parsed = RuleBasedJobParser().parse(
        JobParseInput(
            title="Bilinmeyen Uzman",
            description_raw=fixture_text("minimal_job.txt"),
        )
    )

    assert len(parsed.requirements) == 1
    assert "title_only_parse" in parsed.warnings
    assert "no_skills_detected" in parsed.warnings


def test_empty_fixture_is_rejected() -> None:
    with pytest.raises(EmptyJobDescriptionError):
        RuleBasedJobParser().parse(
            JobParseInput(
                title="Backend Developer",
                description_raw=fixture_text("invalid_empty_job.txt"),
            )
        )


def test_new_graduate_range_is_documented_by_output() -> None:
    parsed = RuleBasedJobParser().parse(
        JobParseInput(
            title="Planning Engineer",
            description_raw=fixture_text("no_experience_job.txt"),
        )
    )

    assert parsed.min_experience_years == 0
    assert parsed.max_experience_years == 1


def test_deduplicate_requirements_is_stable_for_empty_input() -> None:
    assert deduplicate_requirements(()) == ()
