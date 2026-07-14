from types import SimpleNamespace

from app.db.enums import RequirementImportance, RequirementType
from app.domain.matching.engine import RuleBasedMatchingEngine


def _req(
    kind: RequirementType,
    value: str,
    importance: RequirementImportance = RequirementImportance.REQUIRED,
):
    return SimpleNamespace(
        type=kind, raw_value=value, normalized_value=value, importance=importance
    )


def _candidate(**overrides):
    data = {
        "current_title": "Software Engineer",
        "headline": "Python Engineer",
        "experiences": [],
        "skills": [SimpleNamespace(normalized_name="python")],
        "educations": [],
        "languages": [],
        "certifications": [],
        "total_experience_months": 48,
        "city": "Bursa",
        "country": "Turkey",
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def _job(requirements, **overrides):
    data = {
        "title": "Software Engineer",
        "requirements": requirements,
        "min_experience_years": 3,
        "city": "Bursa",
        "country": "Turkey",
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def test_rule_engine_scores_exact_title_skill_and_location() -> None:
    score = RuleBasedMatchingEngine().calculate(
        _job(
            [
                _req(RequirementType.TITLE, "software engineer"),
                _req(RequirementType.SKILL, "python"),
            ]
        ),
        _candidate(),
    )
    assert score.scores["title"] == 100
    assert score.scores["skill"] == 100
    assert score.scores["location"] == 100
    assert 0 <= score.scores["total"] <= 100
    assert "Total fit" in score.explanation


def test_rule_engine_marks_missing_and_uncertain_requirements() -> None:
    score = RuleBasedMatchingEngine().calculate(
        _job([_req(RequirementType.SKILL, "sql"), _req(RequirementType.LANGUAGE, "english")]),
        _candidate(skills=[], languages=[], total_experience_months=None),
    )
    assert score.scores["skill"] == 0
    assert score.scores["experience"] == 0
    assert score.uncertain
