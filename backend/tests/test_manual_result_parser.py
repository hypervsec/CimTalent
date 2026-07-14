from pathlib import Path

import pytest

from app.domain.sourcing.exceptions import ManualImportPayloadTooLargeError
from app.domain.sourcing.types import ManualResultInputData
from app.sourcing.manual_result_parser import MAX_HTML_BYTES, ManualSearchResultParser

FIXTURES = Path(__file__).parent / "fixtures" / "search"


def html_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_json_extracts_normalized_profile_and_display_fields() -> None:
    outcome = ManualSearchResultParser().parse_json(
        (
            ManualResultInputData(
                url="https://tr.linkedin.com/in/demo-one/?trk=x",
                title="Demo Candidate One - Software Engineer | LinkedIn",
                snippet="Python engineer based in Bursa",
                rank=1,
            ),
        )
    )
    result = outcome.results[0]

    assert result.normalized_url == "https://www.linkedin.com/in/demo-one"
    assert result.candidate_profile_slug == "demo-one"
    assert result.displayed_name == "Demo Candidate One"
    assert result.displayed_headline == "Software Engineer"
    assert result.displayed_location == "Bursa"
    assert result.result_rank == 1


def test_url_list_counts_invalid_and_duplicate_values() -> None:
    outcome = ManualSearchResultParser().parse_urls(
        (
            "https://linkedin.com/in/test-profile",
            "https://tr.linkedin.com/in/test-profile/?trk=x",
            "mailto:invalid@example.com",
        )
    )

    assert len(outcome.results) == 1
    assert outcome.duplicate_count == 1
    assert outcome.invalid_count == 1


@pytest.mark.parametrize(
    ("fixture_name", "count"),
    [
        ("google_like_results.html", 2),
        ("generic_results.html", 1),
        ("linkedin_results.html", 1),
        ("mixed_domains.html", 2),
        ("results_without_snippets.html", 1),
    ],
)
def test_static_html_fixtures(fixture_name: str, count: int) -> None:
    outcome = ManualSearchResultParser().parse_html(html_fixture(fixture_name))

    assert len(outcome.results) == count


def test_tracking_html_and_duplicate_html_are_normalized() -> None:
    tracked = ManualSearchResultParser().parse_html(html_fixture("results_with_tracking_urls.html"))
    duplicates = ManualSearchResultParser().parse_html(html_fixture("duplicate_results.html"))

    assert tracked.results[0].normalized_url == "https://example.com/profile/demo?page=2"
    assert len(duplicates.results) == 1
    assert duplicates.duplicate_count == 1


def test_malformed_and_empty_html_do_not_crash() -> None:
    malformed = ManualSearchResultParser().parse_html(html_fixture("malformed_results.html"))
    empty = ManualSearchResultParser().parse_html("<html><script>alert(1)</script></html>")

    assert malformed.results == ()
    assert "no_valid_results_detected" in malformed.warnings
    assert empty.results == ()
    assert "no_valid_results_detected" in empty.warnings


def test_explicit_display_fields_override_title_inference() -> None:
    result = (
        ManualSearchResultParser()
        .parse_json(
            (
                ManualResultInputData(
                    "https://example.com/profile",
                    "Ambiguous - Title | LinkedIn",
                    displayed_name="Test Profile",
                    displayed_headline="Planning Engineer",
                    displayed_location="Kocaeli",
                ),
            )
        )
        .results[0]
    )

    assert result.displayed_name == "Test Profile"
    assert result.displayed_headline == "Planning Engineer"
    assert result.displayed_location == "Kocaeli"


def test_payload_limits() -> None:
    parser = ManualSearchResultParser()
    with pytest.raises(ManualImportPayloadTooLargeError):
        parser.parse_urls(tuple("https://example.com" for _ in range(501)))
    with pytest.raises(ManualImportPayloadTooLargeError):
        parser.parse_html("x" * (MAX_HTML_BYTES + 1))
