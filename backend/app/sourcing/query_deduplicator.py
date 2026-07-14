from app.domain.sourcing.normalizers import normalize_query_key
from app.domain.sourcing.types import GeneratedQuery


def deduplicate_queries(queries: tuple[GeneratedQuery, ...]) -> tuple[GeneratedQuery, ...]:
    output: list[GeneratedQuery] = []
    seen: set[str] = set()
    for query in queries:
        key = normalize_query_key(query.query_text)
        if key not in seen:
            seen.add(key)
            output.append(query)
    return tuple(output)
