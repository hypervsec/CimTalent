import re
from dataclasses import dataclass

from app.db.enums import RequirementImportance, RequirementType
from app.domain.jobs.normalizers import normalize_for_matching
from app.domain.jobs.parser_types import (
    EvidenceUnit,
    ExperienceResult,
    ParsedRequirement,
    requirement_weight,
)

NUMBER = r"(?P<first>\d+(?:[.,]\d+)?)"
SECOND_NUMBER = r"(?P<second>\d+(?:[.,]\d+)?)"
RANGE_YEARS_RE = re.compile(rf"{NUMBER}\s*(?:-|–|ila|to)\s*{SECOND_NUMBER}\s*(?:yil|years?)")
MIN_YEARS_RE = re.compile(rf"(?:en az|minimum|at least)\s*{NUMBER}\s*(?:yil|years?)")
PLUS_YEARS_RE = re.compile(rf"{NUMBER}\s*\+\s*(?:yil|years?)")
MORE_YEARS_RE = re.compile(
    rf"(?:more than\s*)?{NUMBER}\s*(?:yil|years?)\s*(?:ve üzeri|dan fazla|more)?"
)
MONTHS_RE = re.compile(r"(?P<first>\d+(?:[.,]\d+)?)\s*(?:ay|months?)")
NEW_GRAD_RE = re.compile(r"\b(?:yeni mezun|new graduate|entry level)\b")
NO_EXPERIENCE_RE = re.compile(r"\b(?:deneyimsiz|no experience required)\b")


@dataclass(frozen=True, slots=True)
class ExperienceMatch:
    requirement: ParsedRequirement
    minimum: float
    maximum: float | None


class ExperienceParser:
    def parse(self, units: tuple[EvidenceUnit, ...]) -> ExperienceResult:
        matches = tuple(match for unit in units if (match := self._parse_unit(unit)) is not None)
        if not matches:
            return ExperienceResult(requirements=(), min_years=None, max_years=None)

        required = tuple(
            match
            for match in matches
            if match.requirement.importance is RequirementImportance.REQUIRED
        )
        candidates = required or matches
        selected = max(candidates, key=lambda item: item.minimum)
        distinct = {(item.minimum, item.maximum) for item in candidates}
        warnings = ("conflicting_experience_requirements",) if len(distinct) > 1 else ()
        return ExperienceResult(
            requirements=tuple(item.requirement for item in matches),
            min_years=selected.minimum,
            max_years=selected.maximum,
            warnings=warnings,
        )

    def _parse_unit(self, unit: EvidenceUnit) -> ExperienceMatch | None:
        text = normalize_for_matching(unit.text)
        match = RANGE_YEARS_RE.search(text)
        if match is not None:
            minimum = self._number(match.group("first"))
            maximum = self._number(match.group("second"))
            if maximum < minimum:
                return None
            return self._build(unit, minimum, maximum, f"range:{minimum:g}-{maximum:g}")
        match = MIN_YEARS_RE.search(text) or PLUS_YEARS_RE.search(text)
        if match is not None:
            minimum = self._number(match.group("first"))
            return self._build(unit, minimum, None, f"min:{minimum:g}")
        if NO_EXPERIENCE_RE.search(text):
            return self._build(unit, 0.0, None, "min:0", confidence=0.9)
        if NEW_GRAD_RE.search(text):
            return self._build(unit, 0.0, 1.0, "range:0-1", confidence=0.9)
        match = MONTHS_RE.search(text)
        if match is not None:
            minimum = self._number(match.group("first")) / 12
            return self._build(unit, minimum, None, f"min:{minimum:g}")
        match = MORE_YEARS_RE.search(text)
        if match is not None and any(
            marker in text for marker in ("ve üzeri", "dan fazla", "more than")
        ):
            minimum = self._number(match.group("first"))
            return self._build(unit, minimum, None, f"min:{minimum:g}")
        return None

    @staticmethod
    def _build(
        unit: EvidenceUnit,
        minimum: float,
        maximum: float | None,
        normalized: str,
        confidence: float = 0.95,
    ) -> ExperienceMatch:
        requirement = ParsedRequirement(
            type=RequirementType.EXPERIENCE,
            raw_value=unit.text,
            normalized_value=normalized,
            importance=unit.importance,
            weight=requirement_weight(unit.importance),
            confidence=confidence,
            evidence_text=unit.text,
            evidence_start=unit.start,
            evidence_end=unit.end,
        )
        return ExperienceMatch(requirement, minimum, maximum)

    @staticmethod
    def _number(value: str) -> float:
        return float(value.replace(",", "."))
