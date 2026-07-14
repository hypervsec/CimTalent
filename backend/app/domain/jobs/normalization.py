from urllib.parse import urlsplit, urlunsplit


def normalize_duplicate_text(value: str) -> str:
    return value.strip().casefold()


def normalize_source_url(value: str | None) -> str | None:
    if value is None:
        return None
    parts = urlsplit(value.strip())
    normalized_path = parts.path.rstrip("/")
    return urlunsplit(
        (parts.scheme.casefold(), parts.netloc.casefold(), normalized_path, parts.query, "")
    )
