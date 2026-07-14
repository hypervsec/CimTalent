import pytest

from app.db.enums import RequirementImportance, RequirementType
from app.domain.jobs.parser_types import EvidenceUnit, JobParseInput, ParsedRequirement
from app.parsers.jobs.certification_parser import CertificationParser
from app.parsers.jobs.education_parser import EducationParser
from app.parsers.jobs.experience_parser import ExperienceParser
from app.parsers.jobs.language_parser import LanguageParser
from app.parsers.jobs.location_parser import LocationParser
from app.parsers.jobs.orchestrator import deduplicate_requirements
from app.parsers.jobs.skill_parser import SkillParser
from app.parsers.jobs.title_parser import TitleParser


def unit(
    text: str,
    importance: RequirementImportance = RequirementImportance.REQUIRED,
) -> EvidenceUnit:
    return EvidenceUnit(text=text, importance=importance)


@pytest.mark.parametrize(
    ("raw", "normalized"),
    [
        ("Yazılım Geliştirme Uzmanı", "software developer"),
        ("Backend Developer", "backend developer"),
        ("Bilinmeyen Uzman", "bilinmeyen uzman"),
    ],
)
def test_title_parser_normalizes_or_falls_back(raw: str, normalized: str) -> None:
    result = TitleParser().parse(raw, ())

    assert result.requirements[0].normalized_value == normalized
    assert result.requirements[0].confidence == 1


def test_skill_parser_exact_alias_case_and_preferred() -> None:
    result = SkillParser().parse(
        (
            unit("PYTHON, Microsoft SQL Server and RESTful API are required."),
            unit("Docker is a plus.", RequirementImportance.PREFERRED),
        )
    )
    values = {item.normalized_value: item for item in result.requirements}

    assert {"python", "sql server", "rest api", "docker"} <= values.keys()
    assert values["sql server"].confidence == 0.9
    assert values["docker"].importance is RequirementImportance.PREFERRED


def test_skill_parser_avoids_short_word_false_positives_and_duplicates() -> None:
    result = SkillParser().parse((unit("Go to office. C is a letter. Excel and EXCEL."),))

    assert [item.normalized_value for item in result.requirements] == ["excel", "excel"]


def test_skill_parser_manufacturing_aliases() -> None:
    result = SkillParser().parse(
        (unit("Kaynaklı İmalat, Üretim Planlama ve Kalite Kontrol deneyimi"),)
    )

    assert {item.normalized_value for item in result.requirements} >= {
        "welded manufacturing",
        "production planning",
        "quality control",
    }


@pytest.mark.parametrize(
    ("text", "minimum", "maximum", "normalized"),
    [
        ("En az 2 yıl deneyim", 2, None, "min:2"),
        ("2-5 yıl deneyim", 2, 5, "range:2-5"),
        ("5+ years", 5, None, "min:5"),
        ("18 ay deneyim", 1.5, None, "min:1.5"),
        ("Minimum 3 years of experience", 3, None, "min:3"),
        ("3 to 7 years", 3, 7, "range:3-7"),
        ("New graduate", 0, 1, "range:0-1"),
        ("No experience required", 0, None, "min:0"),
    ],
)
def test_experience_patterns(
    text: str, minimum: float, maximum: float | None, normalized: str
) -> None:
    result = ExperienceParser().parse((unit(text),))

    assert result.min_years == minimum
    assert result.max_years == maximum
    assert result.requirements[0].normalized_value == normalized


def test_preferred_experience_does_not_override_required_and_warns_on_conflict() -> None:
    result = ExperienceParser().parse(
        (
            unit("Minimum 3 years", RequirementImportance.REQUIRED),
            unit("Tercihen 5 yıl", RequirementImportance.PREFERRED),
            unit("Minimum 4 years", RequirementImportance.REQUIRED),
        )
    )

    assert result.min_years == 4
    assert "conflicting_experience_requirements" in result.warnings


def test_education_parser_fields_levels_and_related_warning() -> None:
    result = EducationParser().parse(
        (unit("Bilgisayar Mühendisliği veya ilgili bölümlerden lisans mezunu"),)
    )

    assert {item.normalized_value for item in result.requirements} >= {
        "field:computer engineering",
        "level:bachelor",
    }
    assert "related_departments_phrase_detected" in result.warnings


def test_education_parser_supports_multiple_english_fields() -> None:
    result = EducationParser().parse(
        (unit("Bachelor's degree in Mechanical Engineering or Industrial Engineering"),)
    )

    assert {item.normalized_value for item in result.requirements} >= {
        "level:bachelor",
        "field:mechanical engineering",
        "field:industrial engineering",
    }


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("İyi derecede İngilizce", "english:good"),
        ("Fluent English", "english:fluent"),
        ("İleri seviye İngilizce ve Almanca", "english:advanced"),
    ],
)
def test_language_parser_explicit_languages(text: str, expected: str) -> None:
    result = LanguageParser().parse((unit(text),))
    assert expected in {item.normalized_value for item in result.requirements}


def test_language_parser_does_not_infer_from_text_language() -> None:
    assert LanguageParser().parse((unit("This description is written in English."),)).requirements
    assert LanguageParser().parse((unit("Strong communication skills."),)).requirements == ()


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("ISO9001", "iso 9001"),
        ("NDT Level II", "ndt level 2"),
        ("PMP Certificate", "pmp"),
    ],
)
def test_certification_parser_normalizes(text: str, expected: str) -> None:
    result = CertificationParser().parse((unit(text),))
    assert expected in {item.normalized_value for item in result.requirements}


def test_certification_parser_has_no_false_positive() -> None:
    assert CertificationParser().parse((unit("Quality certificate is useful"),)).requirements == ()


def test_location_parser_priorities_modes_and_residence() -> None:
    result = LocationParser().parse(
        JobParseInput(
            title="Developer",
            description_raw="Bursa veya Gemlik'te hibrit çalışabilecek",
            city="Bursa",
            country="Türkiye",
        ),
        (unit("Bursa veya Gemlik'te hibrit çalışabilecek"),),
    )
    values = {item.normalized_value for item in result.requirements}

    assert {"city:bursa", "city:gemlik", "country:turkey", "work_mode:hybrid"} <= values
    assert any(
        item.importance is RequirementImportance.REQUIRED
        for item in result.requirements
        if item.normalized_value == "city:gemlik"
    )


def test_requirement_dedup_required_beats_preferred_and_confidence_is_retained() -> None:
    preferred = ParsedRequirement(
        type=RequirementType.SKILL,
        raw_value="Python",
        normalized_value="python",
        importance=RequirementImportance.PREFERRED,
        weight=0.6,
        confidence=0.95,
    )
    required = ParsedRequirement(
        type=RequirementType.SKILL,
        raw_value="Python bilgisi zorunlu",
        normalized_value="python",
        importance=RequirementImportance.REQUIRED,
        weight=1,
        confidence=0.9,
    )

    result = deduplicate_requirements((preferred, required))

    assert len(result) == 1
    assert result[0].importance is RequirementImportance.REQUIRED
