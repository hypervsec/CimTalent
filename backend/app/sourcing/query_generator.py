import unicodedata

from app.db.enums import RequirementImportance, RequirementType, SearchLanguage, SearchSource
from app.domain.sourcing.constants import GENERIC_SKILLS, LOCATION_ALIASES, TITLE_VARIANTS
from app.domain.sourcing.normalizers import deduplicate_values, normalize_query_key
from app.domain.sourcing.query_strategies import (
    EDUCATION_LOCATION,
    INDUSTRY_TITLE,
    PRECISION,
    RECALL,
    REQUIRED_SKILLS,
    TITLE_LOCATION,
    TITLE_SKILLS,
    QueryStrategy,
)
from app.domain.sourcing.types import GeneratedQuery, QueryGenerationInput
from app.sourcing.query_builder import GoogleXRayQueryBuilder
from app.sourcing.query_deduplicator import deduplicate_queries


class GoogleXRayQueryGenerator:
    def generate(self, data: QueryGenerationInput) -> tuple[GeneratedQuery, ...]:
        builder = GoogleXRayQueryBuilder(data.target_domain)
        canonical_title = self._canonical_title(data)
        required_skills = self._skills(data)
        locations = self._locations(data)
        education = self._requirements(data, RequirementType.EDUCATION)
        industries = self._requirements(data, RequirementType.INDUSTRY)
        output: list[GeneratedQuery] = []

        for language in data.languages:
            titles = self._titles(canonical_title, data.job_title, language, 3)
            output.append(self._build(builder, language, TITLE_LOCATION, titles, (), locations))
        if required_skills:
            for language in data.languages:
                titles = self._titles(canonical_title, data.job_title, language, 2)
                output.append(
                    self._build(
                        builder, language, PRECISION, titles, required_skills[:3], locations
                    )
                )
            for language in data.languages:
                titles = self._titles(canonical_title, data.job_title, language, 3)
                output.append(
                    self._build(builder, language, TITLE_SKILLS, titles, required_skills[:2], ())
                )
        if education:
            language = data.languages[0]
            output.append(
                self._build(builder, language, EDUCATION_LOCATION, education[:2], (), locations)
            )
        if industries:
            language = data.languages[-1]
            titles = self._titles(canonical_title, data.job_title, language, 2)
            output.append(
                self._build(builder, language, INDUSTRY_TITLE, titles, industries[:2], ())
            )
        if required_skills:
            language = data.languages[-1]
            titles = self._titles(canonical_title, data.job_title, language, 2)
            output.append(
                self._build(builder, language, REQUIRED_SKILLS, titles, required_skills[:3], ())
            )
        for language in data.languages:
            titles = self._titles(canonical_title, data.job_title, language, 4)
            output.append(self._build(builder, language, RECALL, titles, (), locations[-1:]))
        return deduplicate_queries(tuple(output))[: data.max_queries]

    @staticmethod
    def _build(
        builder: GoogleXRayQueryBuilder,
        language: SearchLanguage,
        strategy: QueryStrategy,
        titles: tuple[str, ...],
        skills: tuple[str, ...],
        locations: tuple[str, ...],
    ) -> GeneratedQuery:
        text = builder.build(titles=titles, skills=skills, locations=locations)
        return GeneratedQuery(
            source=SearchSource.GOOGLE_XRAY,
            language=language,
            query_text=text,
            query_type=strategy.query_type,
            precision_level=int(strategy.precision),
            expected_intent=strategy.expected_intent,
            included_titles=titles,
            included_skills=skills,
            included_locations=locations,
            normalized_query_key=normalize_query_key(text),
        )

    @staticmethod
    def _canonical_title(data: QueryGenerationInput) -> str:
        for requirement in data.requirements:
            if requirement.type is RequirementType.TITLE:
                return requirement.normalized_value
        return unicodedata.normalize("NFKC", data.job_title).casefold().strip()

    @staticmethod
    def _titles(
        canonical: str,
        fallback: str,
        language: SearchLanguage,
        limit: int,
    ) -> tuple[str, ...]:
        variants = TITLE_VARIANTS.get(canonical)
        if variants is None:
            return deduplicate_values((fallback, canonical))[:limit]
        english, turkish = variants
        selected = turkish if language is SearchLanguage.TR else english
        return deduplicate_values(selected)[:limit]

    @staticmethod
    def _skills(data: QueryGenerationInput) -> tuple[str, ...]:
        candidates = sorted(
            (
                requirement
                for requirement in data.requirements
                if requirement.type is RequirementType.SKILL
                and requirement.importance is RequirementImportance.REQUIRED
                and requirement.normalized_value.casefold() not in GENERIC_SKILLS
            ),
            key=lambda item: (-item.weight, -item.confidence, item.normalized_value.casefold()),
        )
        values = [item.normalized_value for item in candidates]
        values.extend(data.required_skills)
        values.extend(data.preferred_skills)
        return tuple(
            value for value in deduplicate_values(values) if value.casefold() not in GENERIC_SKILLS
        )

    @staticmethod
    def _locations(data: QueryGenerationInput) -> tuple[str, ...]:
        values: list[str] = [value for value in (data.city, data.country) if value]
        values.extend(
            requirement.normalized_value.split(":", 1)[-1]
            for requirement in data.requirements
            if requirement.type is RequirementType.LOCATION
        )
        normalized = [
            LOCATION_ALIASES.get(unicodedata.normalize("NFKC", value).casefold(), value)
            for value in values
        ]
        return deduplicate_values(normalized)

    @staticmethod
    def _requirements(
        data: QueryGenerationInput, requirement_type: RequirementType
    ) -> tuple[str, ...]:
        return deduplicate_values(
            [
                requirement.normalized_value.split(":", 1)[-1]
                for requirement in data.requirements
                if requirement.type is requirement_type
            ]
        )
