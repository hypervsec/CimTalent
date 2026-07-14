from __future__ import annotations

import re
from datetime import date
from urllib.parse import urlsplit

from bs4 import Tag

MONTHS = {
    "jan": 1,
    "january": 1,
    "oca": 1,
    "ocak": 1,
    "feb": 2,
    "february": 2,
    "şub": 2,
    "şubat": 2,
    "mar": 3,
    "march": 3,
    "mart": 3,
    "apr": 4,
    "april": 4,
    "nis": 4,
    "nisan": 4,
    "may": 5,
    "mayıs": 5,
    "jun": 6,
    "june": 6,
    "haz": 6,
    "haziran": 6,
    "jul": 7,
    "july": 7,
    "tem": 7,
    "temmuz": 7,
    "aug": 8,
    "august": 8,
    "ağu": 8,
    "ağustos": 8,
    "sep": 9,
    "september": 9,
    "eyl": 9,
    "eylül": 9,
    "oct": 10,
    "october": 10,
    "eki": 10,
    "ekim": 10,
    "nov": 11,
    "november": 11,
    "kas": 11,
    "kasım": 11,
    "dec": 12,
    "december": 12,
    "ara": 12,
    "aralık": 12,
}
PRESENT = {"present", "current", "günümüz", "halen", "devam ediyor"}


def text(node: Tag | None) -> str | None:
    if node is None:
        return None
    value = " ".join(node.stripped_strings)
    return value or None


def unique_lines(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    result: list[str] = []
    for line in (" ".join(part.split()) for part in value.splitlines()):
        if line and line not in result:
            result.append(line)
    return tuple(result)


def href(node: Tag | None) -> str | None:
    value = node.get("href") if node else None
    if not isinstance(value, str):
        return None
    parts = urlsplit(value.strip())
    return value.strip() if parts.scheme in {"http", "https"} else None


def parse_date_range(value: str | None) -> tuple[date | None, date | None, bool, tuple[str, ...]]:
    raw = (value or "").strip()
    if not raw:
        return None, None, False, ("date_parse_failed",)
    chunks = re.split(r"\s+[–—-]\s+", raw, maxsplit=1)
    if len(chunks) == 1:
        chunks = [chunks[0], ""]
    start = parse_date(chunks[0])
    end_raw = chunks[1].casefold()
    current = end_raw in PRESENT
    end = None if current else parse_date(chunks[1])
    warnings: list[str] = []
    if start is None:
        warnings.append("date_parse_failed")
    if not current and chunks[1].strip() and end is None:
        warnings.append("date_parse_failed")
    if start and end and end < start:
        warnings.append("invalid_date_range")
    return start, end, current, tuple(warnings)


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    match = re.search(r"(?P<year>\d{4})", value)
    if not match:
        return None
    year = int(match.group("year"))
    month = 1
    for name, number in MONTHS.items():
        if re.search(rf"\b{re.escape(name)}\b", value.casefold()):
            month = number
            break
    return date(year, month, 1)


def endorsement_count(value: str | None) -> int | None:
    if not value:
        return None
    match = re.search(r"\b(\d+)\s+(?:endorsements?|yetenek onayı)", value.casefold())
    return int(match.group(1)) if match else None
