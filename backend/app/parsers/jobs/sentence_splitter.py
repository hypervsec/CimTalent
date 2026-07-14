import re
from types import MappingProxyType

from app.db.enums import RequirementImportance
from app.domain.jobs.normalizers import (
    BULLET_RE,
    detect_importance,
    normalize_for_matching,
)
from app.domain.jobs.parser_types import EvidenceUnit, TextSection
from app.domain.jobs.taxonomies import SECTION_TITLES

SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[.!?])\s+")
HEADING_SUFFIX_RE = re.compile(r"\s*:\s*$")
SECTION_LOOKUP = MappingProxyType(
    {normalize_for_matching(title): importance for title, importance in SECTION_TITLES}
)


def split_into_bullets(text: str) -> tuple[str, ...]:
    bullets: list[str] = []
    for line in text.splitlines():
        clean = line.strip()
        if BULLET_RE.match(clean):
            clean = BULLET_RE.sub("", clean).strip()
        if clean:
            bullets.append(clean)
    return tuple(bullets)


def split_into_sentences(text: str) -> tuple[str, ...]:
    sentences: list[str] = []
    for line in split_into_bullets(text):
        sentences.extend(item.strip() for item in SENTENCE_BOUNDARY_RE.split(line) if item.strip())
    return tuple(sentences)


def split_into_sections(text: str) -> tuple[TextSection, ...]:
    lines = text.splitlines(keepends=True)
    sections: list[TextSection] = []
    current_title = ""
    current_normalized = ""
    current_importance = RequirementImportance.OPTIONAL
    current_start = 0
    body_lines: list[str] = []
    offset = 0

    def append_current(end: int) -> None:
        body = "".join(body_lines).strip()
        if body:
            sections.append(
                TextSection(
                    title=current_title,
                    normalized_title=current_normalized,
                    body=body,
                    inferred_importance=current_importance,
                    start=current_start,
                    end=end,
                )
            )

    for line in lines:
        stripped = line.strip()
        heading = HEADING_SUFFIX_RE.sub("", stripped)
        normalized_heading = normalize_for_matching(heading)
        if normalized_heading in SECTION_LOOKUP:
            append_current(offset)
            body_lines = []
            current_title = heading
            current_normalized = normalized_heading
            current_importance = SECTION_LOOKUP[normalized_heading]
            current_start = offset + len(line)
        else:
            body_lines.append(line)
        offset += len(line)
    append_current(len(text))
    return tuple(sections)


def build_evidence_units(text: str, sections: tuple[TextSection, ...]) -> tuple[EvidenceUnit, ...]:
    units: list[EvidenceUnit] = []
    source_sections = sections or (
        TextSection(
            title="",
            normalized_title="",
            body=text,
            inferred_importance=RequirementImportance.OPTIONAL,
            start=0,
            end=len(text),
        ),
    )
    for section in source_sections:
        cursor = section.start
        for sentence in split_into_sentences(section.body):
            found_start = text.find(sentence, cursor)
            start: int | None
            if found_start < 0:
                start = None
                end = None
            else:
                start = found_start
                end = start + len(sentence)
                cursor = end
            units.append(
                EvidenceUnit(
                    text=sentence,
                    importance=detect_importance(sentence, section.inferred_importance),
                    start=start,
                    end=end,
                )
            )
    return tuple(units)
