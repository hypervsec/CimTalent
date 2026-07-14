import pytest

from app.sourcing.profile_url_normalizer import normalize_url


@pytest.mark.parametrize(
    ("raw", "expected", "slug"),
    [
        (
            "https://www.linkedin.com/in/example-name/",
            "https://www.linkedin.com/in/example-name",
            "example-name",
        ),
        (
            "https://tr.linkedin.com/in/example-name?trk=abc#section",
            "https://www.linkedin.com/in/example-name",
            "example-name",
        ),
        (
            "HTTPS://Example.COM:443/a//b/?utm_source=x&page=2#fragment",
            "https://example.com/a/b?page=2",
            None,
        ),
        (
            "https://münich.example/kişiler/demo",
            "https://xn--mnich-kva.example/ki%C5%9Filer/demo",
            None,
        ),
    ],
)
def test_url_normalization(raw: str, expected: str, slug: str | None) -> None:
    result = normalize_url(raw)

    assert result is not None
    assert result.value == expected
    assert result.candidate_profile_slug == slug


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "not a url",
        "javascript:alert(1)",
        "mailto:test@example.com",
        "/relative/path",
        "https://example.com:invalid/path",
    ],
)
def test_invalid_or_unsafe_url_is_rejected(raw: str) -> None:
    assert normalize_url(raw) is None


@pytest.mark.parametrize(
    "raw",
    [
        "https://linkedin.com/company/example",
        "https://linkedin.com/jobs/view/1",
        "https://linkedin.com/school/example",
    ],
)
def test_non_profile_linkedin_url_has_no_candidate_slug(raw: str) -> None:
    result = normalize_url(raw)

    assert result is not None
    assert result.candidate_profile_slug is None


def test_tracking_is_removed_but_business_query_is_preserved() -> None:
    result = normalize_url("https://example.com/profile?trackingId=x&tab=activity&refId=y")

    assert result is not None
    assert result.value == "https://example.com/profile?tab=activity"
