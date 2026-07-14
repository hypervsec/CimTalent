from types import MappingProxyType

from app.db.enums import RequirementType
from app.domain.jobs.normalizers import normalize_for_matching
from app.domain.jobs.parser_types import (
    EvidenceUnit,
    ParsedRequirement,
    ParserFragment,
    requirement_weight,
)
from app.domain.jobs.taxonomies import LANGUAGE_PROFICIENCIES, LANGUAGES
from app.parsers.jobs.phrase_matcher import compile_phrase_patterns, find_phrase_matches

LANGUAGE_PATTERNS = compile_phrase_patterns(tuple(LANGUAGES))
LANGUAGE_VALUES = MappingProxyType(
    {phrase: (value, "language") for phrase, value in LANGUAGES.items()}
)


class LanguageParser:
    def parse(self, units: tuple[EvidenceUnit, ...]) -> ParserFragment:
        requirements: list[ParsedRequirement] = []
        values: list[str] = []
        for unit in units:
            normalized_text = normalize_for_matching(unit.text)
            proficiency = self._proficiency(normalized_text)
            for match in find_phrase_matches(unit.text, LANGUAGE_PATTERNS, LANGUAGE_VALUES):
                normalized = (
                    f"{match.normalized}:{proficiency}" if proficiency else match.normalized
                )
                requirements.append(
                    ParsedRequirement(
                        type=RequirementType.LANGUAGE,
                        raw_value=match.raw,
                        normalized_value=normalized,
                        importance=unit.importance,
                        weight=requirement_weight(unit.importance),
                        confidence=0.95 if proficiency else 0.9,
                        evidence_text=unit.text,
                        evidence_start=unit.start,
                        evidence_end=unit.end,
                    )
                )
                values.append(normalized)
        return ParserFragment(requirements=tuple(requirements), values=tuple(values))

    @staticmethod
    def _proficiency(text: str) -> str | None:
        for phrase in sorted(LANGUAGE_PROFICIENCIES, key=len, reverse=True):
            if phrase in text:
                return LANGUAGE_PROFICIENCIES[phrase]
        return None
