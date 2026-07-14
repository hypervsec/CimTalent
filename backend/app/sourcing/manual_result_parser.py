import re
from collections.abc import Iterable

from bs4 import BeautifulSoup, Tag

from app.domain.sourcing.exceptions import ManualImportPayloadTooLargeError
from app.domain.sourcing.types import (
    ManualParseOutcome,
    ManualResultInputData,
    ParsedManualSearchResult,
)
from app.sourcing.profile_url_normalizer import normalize_url
from app.sourcing.search_result_deduplicator import deduplicate_results

MAX_HTML_BYTES = 2 * 1024 * 1024
MAX_RESULTS = 500
LINKEDIN_SUFFIX_RE = re.compile(r"\s*(?:\||-)\s*LinkedIn\s*$", re.IGNORECASE)
TURKISH_PROFILE_SUFFIX_RE = re.compile(r"\s+adlı kullanıcının profili\s*$", re.IGNORECASE)
KNOWN_LOCATIONS = (
    "Bursa",
    "Istanbul",
    "İstanbul",
    "Kocaeli",
    "Ankara",
    "Izmir",
    "İzmir",
    "Gemlik",
)


class ManualSearchResultParser:
    def parse_json(self, payload: tuple[ManualResultInputData, ...]) -> ManualParseOutcome:
        self._validate_count(len(payload))
        return self._parse_records(payload)

    def parse_urls(self, payload: tuple[str, ...]) -> ManualParseOutcome:
        self._validate_count(len(payload))
        return self._parse_records(tuple(ManualResultInputData(url=value) for value in payload))

    def parse_html(self, payload: str) -> ManualParseOutcome:
        if len(payload.encode("utf-8")) > MAX_HTML_BYTES:
            raise ManualImportPayloadTooLargeError()
        soup = BeautifulSoup(payload, "html.parser")
        for unsafe in soup.select("script, style, noscript"):
            unsafe.decompose()
        containers = soup.select("[data-result], article, .result, .g")
        records = self._records_from_containers(containers)
        if not records:
            records = self._records_from_anchors(soup.find_all("a", href=True))
        outcome = self._parse_records(tuple(records))
        if not outcome.results:
            return ManualParseOutcome(
                received_count=outcome.received_count,
                duplicate_count=outcome.duplicate_count,
                invalid_count=outcome.invalid_count,
                warnings=("no_valid_results_detected",),
                results=(),
            )
        return outcome

    def _parse_records(self, records: tuple[ManualResultInputData, ...]) -> ManualParseOutcome:
        parsed: list[ParsedManualSearchResult] = []
        invalid = 0
        for record in records:
            normalized = normalize_url(record.url)
            if normalized is None:
                invalid += 1
                continue
            name, headline = self._display_fields(record.title)
            parsed.append(
                ParsedManualSearchResult(
                    source_url=record.url.strip(),
                    normalized_url=normalized.value,
                    source_domain=normalized.source_domain,
                    title=self._clean(record.title),
                    snippet=self._clean(record.snippet),
                    displayed_name=self._clean(record.displayed_name) or name,
                    displayed_headline=self._clean(record.displayed_headline) or headline,
                    displayed_location=self._clean(record.displayed_location)
                    or self._location(record.snippet),
                    result_rank=record.rank,
                    candidate_profile_slug=normalized.candidate_profile_slug,
                )
            )
        unique, duplicates = deduplicate_results(tuple(parsed))
        return ManualParseOutcome(
            received_count=len(records),
            duplicate_count=duplicates,
            invalid_count=invalid,
            warnings=(),
            results=unique,
        )

    @staticmethod
    def _records_from_containers(containers: Iterable[Tag]) -> list[ManualResultInputData]:
        records: list[ManualResultInputData] = []
        for rank, container in enumerate(containers, start=1):
            anchor = container.find("a", href=True)
            if not isinstance(anchor, Tag):
                continue
            title_attr = anchor.get("title")
            title = anchor.get_text(" ", strip=True) or (
                title_attr if isinstance(title_attr, str) else None
            )
            snippet_node = container.select_one(".snippet, .description, p")
            snippet = (
                snippet_node.get_text(" ", strip=True) if isinstance(snippet_node, Tag) else None
            )
            href = anchor.get("href")
            if isinstance(href, str):
                records.append(ManualResultInputData(href, title, snippet, rank=rank))
        return records

    @staticmethod
    def _records_from_anchors(anchors: Iterable[Tag]) -> list[ManualResultInputData]:
        records: list[ManualResultInputData] = []
        for rank, anchor in enumerate(anchors, start=1):
            href = anchor.get("href")
            title = anchor.get_text(" ", strip=True) or anchor.get("title")
            if isinstance(href, str) and isinstance(title, str) and len(title.strip()) >= 3:
                parent_text = anchor.parent.get_text(" ", strip=True) if anchor.parent else ""
                snippet = parent_text.replace(title, "", 1).strip() or None
                records.append(ManualResultInputData(href, title, snippet, rank=rank))
        return records

    @staticmethod
    def _display_fields(title: str | None) -> tuple[str | None, str | None]:
        clean = ManualSearchResultParser._clean(title)
        if clean is None:
            return None, None
        clean = LINKEDIN_SUFFIX_RE.sub("", clean).strip()
        clean = TURKISH_PROFILE_SUFFIX_RE.sub("", clean).strip()
        parts = tuple(part.strip() for part in clean.split(" - ") if part.strip())
        if len(parts) == 1:
            return parts[0], None
        if len(parts) in {2, 3}:
            return parts[0], parts[1]
        return None, None

    @staticmethod
    def _location(snippet: str | None) -> str | None:
        if snippet is None:
            return None
        folded = snippet.casefold()
        return next(
            (location for location in KNOWN_LOCATIONS if location.casefold() in folded),
            None,
        )

    @staticmethod
    def _clean(value: object) -> str | None:
        if not isinstance(value, str):
            return None
        clean = " ".join(value.split()).strip()
        return clean or None

    @staticmethod
    def _validate_count(count: int) -> None:
        if count > MAX_RESULTS:
            raise ManualImportPayloadTooLargeError()
