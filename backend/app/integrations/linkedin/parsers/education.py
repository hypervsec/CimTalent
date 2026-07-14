from hashlib import sha256
from typing import cast

from app.domain.enrichment.normalizers import normalize_education
from app.domain.enrichment.types import EnrichedEducation
from app.domain.linkedin.types import ParserResult
from app.integrations.linkedin.parser_context import ParserContext
from app.integrations.linkedin.parsers.common import parse_date_range, text


class EducationParser:
    def parse(self, context: ParserContext) -> ParserResult[EnrichedEducation]:
        section, selector = context.selector_registry.first(context.soup, "education.list")
        if section is None:
            return ParserResult(warnings=("section_empty",), is_partial=True)
        items, item_selector = context.selector_registry.all(section, "education.item")
        result: list[EnrichedEducation] = []
        for index, item in enumerate(items[: context.limits.educations]):
            institution = text(item.select_one("[data-field='institution'], .institution, h3, h4"))
            if not institution:
                continue
            degree_field = text(
                item.select_one("[data-field='degree-field'], .degree-field, p.degree")
            )
            degree, field = _split_degree_field(degree_field)
            start, end, _, _ = parse_date_range(
                text(item.select_one("[data-field='date'], .date-range, time"))
            )
            raw = EnrichedEducation(
                institution_name=institution,
                external_key=cast(str | None, item.get("data-external-key"))
                or sha256(f"{institution}|{degree}|{field}|{start}|{end}".encode()).hexdigest()[
                    :24
                ],
                degree=degree,
                field_of_study=field,
                start_year=start.year if start else None,
                end_year=end.year if end else None,
                grade=text(item.select_one("[data-field='grade'], .grade")),
                description=text(item.select_one("[data-field='description'], .description")),
                source="linkedin",
                confidence=0.95,
                sort_order=index,
            )
            result.append(normalize_education(raw))
        return ParserResult(
            items=tuple(result), selectors_used=tuple(x for x in (selector, item_selector) if x)
        )


def _split_degree_field(value: str | None) -> tuple[str | None, str | None]:
    if not value:
        return None, None
    if "," not in value:
        return value.strip(), None
    degree, field = value.split(",", 1)
    return degree.strip() or None, field.strip() or None
