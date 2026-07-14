from hashlib import sha256
from typing import cast

from app.domain.enrichment.normalizers import normalize_skill_name, normalize_title
from app.domain.enrichment.types import EnrichedExperience
from app.domain.linkedin.types import ParserResult
from app.integrations.linkedin.parser_context import ParserContext
from app.integrations.linkedin.parsers.common import href, parse_date_range, text, unique_lines


class ExperienceParser:
    def parse(self, context: ParserContext) -> ParserResult[EnrichedExperience]:
        section, selector = context.selector_registry.first(context.soup, "experience.list")
        if section is None:
            return ParserResult(warnings=("section_empty",), is_partial=True)
        items, item_selector = context.selector_registry.all(section, "experience.item")
        result: list[EnrichedExperience] = []
        warnings: list[str] = []
        for index, item in enumerate(items[: context.limits.experiences]):
            title_node = item.select_one("[data-field='title'], .position-title, h3, h4")
            company_node = item.select_one("[data-field='company'], .company-name, p.company")
            date_node = item.select_one("[data-field='date'], .date-range, time")
            title = text(title_node)
            if not title:
                warnings.append("item_parse_failed")
                continue
            company = text(company_node)
            date_start, date_end, current, date_warnings = parse_date_range(text(date_node))
            warnings.extend(date_warnings)
            employment = item.get("data-employment-type")
            company_url = href(company_node.find("a") if company_node else None)
            fingerprint = sha256(
                f"{title}|{company}|{date_start}|{date_end}|{current}".encode()
            ).hexdigest()[:24]
            skills = tuple(
                dict.fromkeys(
                    normalize_skill_name(word)[0]
                    for word in unique_lines(cast(str | None, item.get("data-skills")))
                )
            )
            result.append(
                EnrichedExperience(
                    position_title_raw=title,
                    external_key=cast(str | None, item.get("data-external-key"))
                    or f"linkedin:{fingerprint}",
                    position_title_normalized=normalize_title(title),
                    company_name=company,
                    company_url=company_url,
                    employment_type=str(employment) if employment else None,
                    location=text(item.select_one("[data-field='location'], .location")),
                    start_date=date_start,
                    end_date=date_end,
                    is_current=current,
                    description=text(item.select_one("[data-field='description'], .description")),
                    skills_detected=skills,
                    source="linkedin",
                    confidence=0.95,
                    sort_order=index,
                )
            )
        return ParserResult(
            items=tuple(result),
            warnings=tuple(warnings),
            is_partial=bool(warnings),
            selectors_used=tuple(x for x in (selector, item_selector) if x),
        )
