import re

from app.db.enums import RequirementImportance, RequirementType
from app.domain.jobs.normalizers import deduplicate_strings, normalize_for_matching
from app.domain.jobs.parser_types import (
    EvidenceUnit,
    ParsedRequirement,
    ParserFragment,
    requirement_weight,
)
from app.domain.jobs.taxonomies import TITLE_ALIASES

TITLE_LABEL_RE = re.compile(r"(?im)^\s*(?:pozisyon|position|role)\s*:\s*(?P<title>[^\n]+)$")


class TitleParser:
    @staticmethod
    def _normalize_title(value: str) -> str:
        normalized = normalize_for_matching(value)
        for alias, canonical in TITLE_ALIASES.items():
            if normalize_for_matching(alias) == normalized:
                return canonical
        return normalized

    def parse(self, title: str, units: tuple[EvidenceUnit, ...]) -> ParserFragment:
        raw_title = title.strip()
        normalized = self._normalize_title(raw_title)
        candidates = [normalized]
        for unit in units:
            match = TITLE_LABEL_RE.search(unit.text)
            if match is not None:
                candidate = match.group("title").strip()
                candidates.append(self._normalize_title(candidate))
        requirement = ParsedRequirement(
            type=RequirementType.TITLE,
            raw_value=raw_title,
            normalized_value=normalized,
            importance=RequirementImportance.REQUIRED,
            weight=requirement_weight(RequirementImportance.REQUIRED),
            confidence=1.0,
            evidence_text=raw_title,
        )
        return ParserFragment(requirements=(requirement,), values=deduplicate_strings(candidates))
