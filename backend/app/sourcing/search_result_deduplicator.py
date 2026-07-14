from app.domain.sourcing.types import ParsedManualSearchResult


def deduplicate_results(
    results: tuple[ParsedManualSearchResult, ...],
) -> tuple[tuple[ParsedManualSearchResult, ...], int]:
    output: list[ParsedManualSearchResult] = []
    seen_urls: set[str] = set()
    seen_slugs: set[str] = set()
    duplicate_count = 0
    for result in results:
        slug = result.candidate_profile_slug
        if result.normalized_url in seen_urls or (slug is not None and slug in seen_slugs):
            duplicate_count += 1
            continue
        seen_urls.add(result.normalized_url)
        if slug is not None:
            seen_slugs.add(slug)
        output.append(result)
    return tuple(output), duplicate_count
