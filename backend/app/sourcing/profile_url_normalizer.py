import re
from dataclasses import dataclass
from urllib.parse import parse_qsl, quote, unquote, urlencode, urlsplit, urlunsplit

TRACKING_PARAMETERS = frozenset(
    {
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_term",
        "utm_content",
        "trk",
        "trackingid",
        "ref",
        "refid",
        "sessionid",
        "lipi",
        "midtoken",
    }
)
PATH_SLASH_RE = re.compile(r"/{2,}")
LINKEDIN_PROFILE_RE = re.compile(r"^/in/(?P<slug>[^/?#]+)", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class NormalizedUrl:
    value: str
    source_domain: str
    candidate_profile_slug: str | None


def normalize_url(raw_url: str) -> NormalizedUrl | None:
    clean = raw_url.strip()
    if not clean:
        return None
    try:
        parsed = urlsplit(clean)
        if parsed.scheme.casefold() not in {"http", "https"} or not parsed.hostname:
            return None
        scheme = parsed.scheme.casefold()
        host = parsed.hostname.encode("idna").decode("ascii").casefold()
        port_value = parsed.port
    except (UnicodeError, ValueError):
        return None
    port = ""
    if port_value is not None and not (
        (scheme == "http" and port_value == 80) or (scheme == "https" and port_value == 443)
    ):
        port = f":{port_value}"
    path = PATH_SLASH_RE.sub("/", parsed.path or "/")
    path = quote(unquote(path), safe="/:@-._~!$&'()*+,;=")
    if path != "/":
        path = path.rstrip("/")
    query_items = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key.casefold() not in TRACKING_PARAMETERS
    ]
    query = urlencode(query_items, doseq=True)
    linkedin_slug = _linkedin_slug(host, path)
    if linkedin_slug is not None:
        canonical = f"https://www.linkedin.com/in/{quote(linkedin_slug, safe='-._~')}"
        return NormalizedUrl(canonical, "linkedin.com", linkedin_slug)
    normalized = urlunsplit((scheme, f"{host}{port}", path, query, ""))
    return NormalizedUrl(normalized, host, None)


def _linkedin_slug(host: str, path: str) -> str | None:
    if host != "linkedin.com" and not host.endswith(".linkedin.com"):
        return None
    match = LINKEDIN_PROFILE_RE.match(path)
    if match is None:
        return None
    slug = unquote(match.group("slug")).strip()
    return slug or None
