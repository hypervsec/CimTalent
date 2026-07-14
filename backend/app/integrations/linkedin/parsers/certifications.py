from app.domain.enrichment.normalizers import normalize_certification
from app.domain.enrichment.types import EnrichedCertification
from app.domain.linkedin.types import ParserResult
from app.integrations.linkedin.parser_context import ParserContext
from app.integrations.linkedin.parsers.common import href, parse_date, text


class CertificationsParser:
    def parse(self, context: ParserContext) -> ParserResult[EnrichedCertification]:
        section, selector = context.selector_registry.first(context.soup, "certifications.list")
        if section is None:
            return ParserResult(warnings=("section_empty",), is_partial=True)
        items, item_selector = context.selector_registry.all(section, "certifications.item")
        result: list[EnrichedCertification] = []
        for item in items[: context.limits.certifications]:
            name = text(item.select_one("[data-field='name'], .certification-name, h3, h4"))
            if not name:
                continue
            issue = parse_date(text(item.select_one("[data-field='issue-date'], .issue-date")))
            expiration = parse_date(
                text(item.select_one("[data-field='expiration-date'], .expiration-date"))
            )
            raw = EnrichedCertification(
                name=name,
                issuer=text(item.select_one("[data-field='issuer'], .issuer")),
                issue_date=issue,
                expiration_date=expiration,
                credential_id=text(item.select_one("[data-field='credential-id'], .credential-id")),
                credential_url=href(item.select_one("a[href]")),
                source="linkedin",
                confidence=0.95,
            )
            result.append(normalize_certification(raw))
        return ParserResult(
            items=tuple(result), selectors_used=tuple(x for x in (selector, item_selector) if x)
        )
