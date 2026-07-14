import re
from collections.abc import Mapping
from dataclasses import dataclass

from app.domain.jobs.normalizers import normalize_for_matching


@dataclass(frozen=True, slots=True)
class PhraseMatch:
    raw: str
    normalized: str
    category: str
    confidence: float
    start: int
    end: int


def compile_phrase_patterns(phrases: tuple[str, ...]) -> tuple[tuple[str, re.Pattern[str]], ...]:
    ordered = sorted(phrases, key=lambda item: (-len(item), item))
    return tuple(
        (
            phrase,
            re.compile(rf"(?<!\w){re.escape(normalize_for_matching(phrase))}(?!\w)"),
        )
        for phrase in ordered
    )


def find_phrase_matches(
    text: str,
    patterns: tuple[tuple[str, re.Pattern[str]], ...],
    normalized_values: Mapping[str, tuple[str, str]],
) -> tuple[PhraseMatch, ...]:
    normalized_text = normalize_for_matching(text)
    candidates: list[PhraseMatch] = []
    for phrase, pattern in patterns:
        normalized, category = normalized_values[phrase]
        confidence = 0.95 if normalize_for_matching(phrase) == normalized else 0.90
        for match in pattern.finditer(normalized_text):
            candidates.append(
                PhraseMatch(
                    raw=text[match.start() : match.end()],
                    normalized=normalized,
                    category=category,
                    confidence=confidence,
                    start=match.start(),
                    end=match.end(),
                )
            )
    selected: list[PhraseMatch] = []
    for candidate in sorted(candidates, key=lambda item: (item.start, -(item.end - item.start))):
        if any(candidate.start < item.end and candidate.end > item.start for item in selected):
            continue
        selected.append(candidate)
    return tuple(selected)
