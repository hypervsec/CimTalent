import re
import unicodedata
from urllib.parse import urlsplit

from app.domain.sourcing.exceptions import InvalidTargetDomainError

WHITESPACE_RE = re.compile(r"\s+")
DOMAIN_RE = re.compile(r"^[a-z0-9.-]+(?::\d+)?(?:/[A-Za-z0-9._~!$&'()*+,;=:@%/-]*)?$")
CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")


def normalize_query_key(query: str) -> str:
    normalized = unicodedata.normalize("NFKC", query).casefold()
    return WHITESPACE_RE.sub(" ", normalized).strip()


def normalize_target_domain(value: str) -> str:
    clean = unicodedata.normalize("NFKC", value).strip()
    if not clean or CONTROL_RE.search(clean):
        raise InvalidTargetDomainError()
    parsed = urlsplit(clean if "://" in clean else f"https://{clean}")
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise InvalidTargetDomainError()
    host = parsed.hostname.encode("idna").decode("ascii").lower()
    try:
        parsed_port = parsed.port
    except ValueError as exc:
        raise InvalidTargetDomainError() from exc
    port = f":{parsed_port}" if parsed_port not in {None, 80, 443} else ""
    path = re.sub(r"/{2,}", "/", parsed.path).rstrip("/")
    normalized = f"{host}{port}{path}"
    if parsed.query or parsed.fragment or not DOMAIN_RE.fullmatch(normalized):
        raise InvalidTargetDomainError()
    return normalized


def deduplicate_values(values: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        clean = WHITESPACE_RE.sub(" ", value).strip()
        key = unicodedata.normalize("NFKC", clean).casefold()
        if clean and key not in seen:
            seen.add(key)
            result.append(clean)
    return tuple(result)
