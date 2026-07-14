from uuid import uuid4

import pytest

from app.db.enums import RequirementImportance, RequirementType, SearchLanguage
from app.domain.sourcing.exceptions import InvalidTargetDomainError, QueryGenerationError
from app.domain.sourcing.normalizers import normalize_query_key, normalize_target_domain
from app.domain.sourcing.types import QueryGenerationInput, QueryRequirementInput, QueryType
from app.sourcing.query_builder import GoogleXRayQueryBuilder
from app.sourcing.query_generator import GoogleXRayQueryGenerator


def requirement(
    requirement_type: RequirementType,
    value: str,
    importance: RequirementImportance = RequirementImportance.REQUIRED,
    weight: float = 1.0,
    confidence: float = 0.95,
) -> QueryRequirementInput:
    return QueryRequirementInput(requirement_type, value, value, importance, weight, confidence)


def input_data(**changes: object) -> QueryGenerationInput:
    values: dict[str, object] = {
        "job_id": uuid4(),
        "job_title": "Yazılım Geliştirme Uzmanı",
        "city": "Bursa",
        "country": "Türkiye",
        "required_skills": ("Python", "SQL Server", "REST API"),
        "preferred_skills": ("Docker",),
        "keywords_tr": (),
        "keywords_en": (),
        "requirements": (
            requirement(RequirementType.TITLE, "software developer"),
            requirement(RequirementType.SKILL, "Python"),
            requirement(RequirementType.SKILL, "SQL Server", confidence=0.9),
            requirement(RequirementType.EDUCATION, "field:computer engineering"),
            requirement(RequirementType.INDUSTRY, "software"),
        ),
        "max_queries": 10,
        "languages": (SearchLanguage.TR, SearchLanguage.EN),
        "target_domain": "linkedin.com/in",
    }
    values.update(changes)
    return QueryGenerationInput(**values)  # type: ignore[arg-type]


def test_generator_is_deterministic_and_respects_maximum() -> None:
    generator = GoogleXRayQueryGenerator()
    data = input_data(max_queries=5)

    assert generator.generate(data) == generator.generate(data)
    assert len(generator.generate(data)) == 5


def test_generator_creates_tr_en_strategies_in_stable_order() -> None:
    queries = GoogleXRayQueryGenerator().generate(input_data())

    assert [(item.language, item.query_type) for item in queries[:6]] == [
        (SearchLanguage.TR, QueryType.TITLE_LOCATION),
        (SearchLanguage.EN, QueryType.TITLE_LOCATION),
        (SearchLanguage.TR, QueryType.PRECISION),
        (SearchLanguage.EN, QueryType.PRECISION),
        (SearchLanguage.TR, QueryType.TITLE_SKILLS),
        (SearchLanguage.EN, QueryType.TITLE_SKILLS),
    ]
    assert {QueryType.EDUCATION_LOCATION, QueryType.INDUSTRY_TITLE} <= {
        item.query_type for item in queries
    }


def test_domain_titles_skills_locations_and_intent_are_populated() -> None:
    queries = GoogleXRayQueryGenerator().generate(input_data())

    assert all(item.query_text.startswith("site:linkedin.com/in") for item in queries)
    assert all(item.included_titles and item.expected_intent for item in queries)
    assert any(
        "Yazılım" in item.query_text for item in queries if item.language is SearchLanguage.TR
    )
    assert any(
        "Software" in item.query_text for item in queries if item.language is SearchLanguage.EN
    )
    assert any("Python" in item.included_skills for item in queries)
    assert any("Bursa" in item.included_locations for item in queries)
    assert {item.precision_level for item in queries} <= {1, 3, 4, 5}


def test_language_filter_and_unknown_title_fallback() -> None:
    data = input_data(
        job_title="Unique Quantum Architect",
        requirements=(),
        languages=(SearchLanguage.EN,),
        city=None,
        country=None,
        required_skills=(),
        preferred_skills=(),
    )

    queries = GoogleXRayQueryGenerator().generate(data)

    assert queries
    assert all(item.language is SearchLanguage.EN for item in queries)
    assert all("Unique Quantum Architect" in item.query_text for item in queries)


def test_required_skill_priority_and_generic_exclusion() -> None:
    data = input_data(
        requirements=(
            requirement(RequirementType.TITLE, "software developer"),
            requirement(RequirementType.SKILL, "communication", weight=2),
            requirement(RequirementType.SKILL, "FastAPI", confidence=1),
            requirement(
                RequirementType.SKILL,
                "Docker",
                RequirementImportance.PREFERRED,
                confidence=1,
            ),
        )
    )

    queries = GoogleXRayQueryGenerator().generate(data)

    used = tuple(skill for query in queries for skill in query.included_skills)
    assert "communication" not in used
    assert "FastAPI" in used
    assert "Docker" not in used


def test_query_key_collapses_case_and_whitespace() -> None:
    assert normalize_query_key('SITE:LINKEDIN.COM/IN   "python"   Bursa') == normalize_query_key(
        'site:linkedin.com/in "Python" Bursa'
    )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("linkedin.com/in/", "linkedin.com/in"),
        ("HTTPS://LinkedIn.com/in", "linkedin.com/in"),
        ("münich.example/profiles", "xn--mnich-kva.example/profiles"),
    ],
)
def test_target_domain_normalization(raw: str, expected: str) -> None:
    assert normalize_target_domain(raw) == expected


@pytest.mark.parametrize(
    "raw", ["", "linkedin.com/in?x=1", "javascript:alert(1)", "linkedin.com/in\nother"]
)
def test_invalid_target_domain_is_rejected(raw: str) -> None:
    with pytest.raises(InvalidTargetDomainError):
        normalize_target_domain(raw)


def test_builder_escapes_quotes_removes_empty_and_groups_or() -> None:
    query = GoogleXRayQueryBuilder("linkedin.com/in").build(
        titles=('Backend "Developer"', "Software Engineer"),
        skills=("", "Python", "C#"),
    )

    assert '"Backend Developer"' in query
    assert '("Python" OR "C#")' in query
    assert "  " not in query


def test_builder_trims_optional_parts_but_keeps_domain_and_title() -> None:
    builder = GoogleXRayQueryBuilder("linkedin.com/in", max_length=80)
    query = builder.build(
        titles=("Software Developer",),
        skills=("Very Long Distinctive Skill Name" * 4,),
        locations=("Very Long Location Name" * 4,),
    )

    assert len(query) <= 80
    assert query.startswith("site:linkedin.com/in")
    assert '"Software Developer"' in query


def test_builder_requires_a_title() -> None:
    with pytest.raises(QueryGenerationError):
        GoogleXRayQueryBuilder("linkedin.com/in").build(titles=(" ",))


def test_builder_rejects_limit_smaller_than_required_domain() -> None:
    with pytest.raises(QueryGenerationError):
        GoogleXRayQueryBuilder("linkedin.com/in", max_length=10).build(titles=("Developer",))
