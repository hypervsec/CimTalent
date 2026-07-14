import pytest
from pydantic import ValidationError

from app.db.enums import JobSource
from app.schemas.jobs import JobCreate, JobUpdate


def valid_payload() -> dict[str, object]:
    return {
        "company_name": " Example Company ",
        "title": " Backend Developer ",
        "description_raw": " Build APIs ",
    }


def test_valid_job_create_trims_required_text() -> None:
    job = JobCreate.model_validate(valid_payload())

    assert job.company_name == "Example Company"
    assert job.title == "Backend Developer"
    assert job.description_raw == "Build APIs"
    assert job.source is JobSource.MANUAL


@pytest.mark.parametrize("field", ["company_name", "title", "description_raw"])
def test_job_create_rejects_blank_required_text(field: str) -> None:
    payload = valid_payload()
    payload[field] = "   "

    with pytest.raises(ValidationError):
        JobCreate.model_validate(payload)


@pytest.mark.parametrize("field", ["min_experience_years", "max_experience_years"])
def test_job_create_rejects_negative_experience(field: str) -> None:
    payload = valid_payload()
    payload[field] = -1

    with pytest.raises(ValidationError):
        JobCreate.model_validate(payload)


def test_job_create_rejects_reversed_experience_range() -> None:
    payload = valid_payload() | {"min_experience_years": 4, "max_experience_years": 2}

    with pytest.raises(ValidationError):
        JobCreate.model_validate(payload)


def test_non_manual_source_requires_url() -> None:
    payload = valid_payload() | {"source": "linkedin"}

    with pytest.raises(ValidationError):
        JobCreate.model_validate(payload)


def test_manual_source_allows_missing_url() -> None:
    assert JobCreate.model_validate(valid_payload()).source_url is None


def test_string_lists_are_trimmed_and_case_insensitively_deduplicated() -> None:
    payload = valid_payload() | {"required_skills": [" Python ", "python", "SQL"]}

    job = JobCreate.model_validate(payload)

    assert job.required_skills == ["Python", "SQL"]


@pytest.mark.parametrize("url", ["not-a-url", "ftp://example.test/job"])
def test_source_url_must_be_http_url(url: str) -> None:
    payload = valid_payload() | {"source_url": url}

    with pytest.raises(ValidationError):
        JobCreate.model_validate(payload)


def test_source_url_length_is_limited() -> None:
    payload = valid_payload() | {"source_url": "https://example.test/" + "a" * 2048}

    with pytest.raises(ValidationError):
        JobCreate.model_validate(payload)


def test_job_update_accepts_partial_and_empty_payloads() -> None:
    assert JobUpdate.model_validate({}).model_dump(exclude_unset=True) == {}
    update = JobUpdate.model_validate({"title": " New title "})
    assert update.model_dump(exclude_unset=True) == {"title": "New title"}


@pytest.mark.parametrize("items", [[""], ["  "], [1], "Python"])
def test_invalid_string_list_item_is_rejected(items: object) -> None:
    payload = valid_payload() | {"required_skills": items}

    with pytest.raises(ValidationError):
        JobCreate.model_validate(payload)
