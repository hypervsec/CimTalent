from dataclasses import replace
from types import MappingProxyType

from app.db.enums import RequirementImportance, RequirementType
from app.domain.jobs.normalizers import clean_job_text, deduplicate_strings
from app.domain.jobs.parser_exceptions import EmptyJobDescriptionError
from app.domain.jobs.parser_types import (
    JobParseInput,
    ParsedJobData,
    ParsedRequirement,
)
from app.domain.jobs.taxonomies import TITLE_VARIANTS_TR
from app.parsers.jobs.certification_parser import CertificationParser
from app.parsers.jobs.education_parser import EducationParser
from app.parsers.jobs.experience_parser import ExperienceParser
from app.parsers.jobs.industry_parser import IndustryParser
from app.parsers.jobs.language_parser import LanguageParser
from app.parsers.jobs.location_parser import LocationParser
from app.parsers.jobs.sentence_splitter import build_evidence_units, split_into_sections
from app.parsers.jobs.skill_parser import SkillParser
from app.parsers.jobs.title_parser import TitleParser

PARSER_VERSION = "rule-based-v1"
IMPORTANCE_RANK = MappingProxyType(
    {
        RequirementImportance.OPTIONAL: 0,
        RequirementImportance.PREFERRED: 1,
        RequirementImportance.REQUIRED: 2,
    }
)


def deduplicate_requirements(
    requirements: tuple[ParsedRequirement, ...],
) -> tuple[ParsedRequirement, ...]:
    selected: dict[tuple[RequirementType, str], ParsedRequirement] = {}
    for requirement in requirements:
        key = (requirement.type, requirement.normalized_value.casefold())
        current = selected.get(key)
        if current is None:
            selected[key] = requirement
            continue
        current_rank = IMPORTANCE_RANK[current.importance]
        candidate_rank = IMPORTANCE_RANK[requirement.importance]
        if candidate_rank > current_rank:
            selected[key] = requirement
            continue
        if candidate_rank == current_rank and requirement.confidence > current.confidence:
            selected[key] = requirement
            continue
        if candidate_rank == current_rank and requirement.confidence == current.confidence:
            current_evidence = current.evidence_text or current.raw_value
            candidate_evidence = requirement.evidence_text or requirement.raw_value
            if len(candidate_evidence) > len(current_evidence):
                selected[key] = replace(
                    requirement,
                    confidence=max(current.confidence, requirement.confidence),
                )
    return tuple(selected.values())


class JobParserOrchestrator:
    def __init__(self) -> None:
        self.title_parser = TitleParser()
        self.skill_parser = SkillParser()
        self.experience_parser = ExperienceParser()
        self.education_parser = EducationParser()
        self.language_parser = LanguageParser()
        self.certification_parser = CertificationParser()
        self.location_parser = LocationParser()
        self.industry_parser = IndustryParser()

    def parse(self, data: JobParseInput) -> ParsedJobData:
        description_clean = clean_job_text(data.description_raw)
        if not description_clean:
            raise EmptyJobDescriptionError()
        sections = split_into_sections(description_clean)
        units = build_evidence_units(description_clean, sections)

        title = self.title_parser.parse(data.title, units)
        skills = self.skill_parser.parse(units)
        experience = self.experience_parser.parse(units)
        education = self.education_parser.parse(units)
        languages = self.language_parser.parse(units)
        certifications = self.certification_parser.parse(units)
        locations = self.location_parser.parse(data, units)
        industries = self.industry_parser.parse(units)

        requirements = deduplicate_requirements(
            (
                *title.requirements,
                *skills.requirements,
                *experience.requirements,
                *education.requirements,
                *languages.requirements,
                *certifications.requirements,
                *locations.requirements,
                *industries.requirements,
            )
        )
        required_skills = deduplicate_strings(
            [
                item.normalized_value
                for item in requirements
                if item.type is RequirementType.SKILL
                and item.importance is RequirementImportance.REQUIRED
            ]
        )
        preferred_skills = deduplicate_strings(
            [
                item.normalized_value
                for item in requirements
                if item.type is RequirementType.SKILL
                and item.importance is RequirementImportance.PREFERRED
            ]
        )
        education_fields = deduplicate_strings(
            [
                item.normalized_value.removeprefix("field:")
                for item in requirements
                if item.type is RequirementType.EDUCATION
                and item.normalized_value.startswith("field:")
            ]
        )
        education_levels = deduplicate_strings(
            [
                item.normalized_value.removeprefix("level:")
                for item in requirements
                if item.type is RequirementType.EDUCATION
                and item.normalized_value.startswith("level:")
            ]
        )
        location_values = deduplicate_strings(
            [
                item.normalized_value
                for item in requirements
                if item.type is RequirementType.LOCATION
            ]
        )
        language_values = deduplicate_strings(
            [
                item.normalized_value
                for item in requirements
                if item.type is RequirementType.LANGUAGE
            ]
        )
        certification_values = deduplicate_strings(
            [
                item.normalized_value
                for item in requirements
                if item.type is RequirementType.CERTIFICATION
            ]
        )
        industry_values = deduplicate_strings(
            [
                item.normalized_value
                for item in requirements
                if item.type is RequirementType.INDUSTRY
            ]
        )

        warnings = [
            *experience.warnings,
            *education.warnings,
        ]
        if not skills.requirements:
            warnings.append("no_skills_detected")
        if not experience.requirements:
            warnings.append("no_experience_detected")
        if not education.requirements:
            warnings.append("no_education_detected")
        if len(requirements) == 1:
            warnings.append("title_only_parse")

        confidence = self._confidence(
            has_title=bool(title.requirements),
            has_skill=bool(skills.requirements),
            has_experience=bool(experience.requirements),
            has_education=bool(education.requirements),
            has_location=bool(locations.requirements),
            has_language=bool(languages.requirements),
            has_sections=any(section.title for section in sections),
        )
        if confidence < 0.4:
            warnings.append("parser_low_confidence")

        keywords_tr, keywords_en = self._keywords(
            title.values,
            required_skills,
            preferred_skills,
            education_fields,
            location_values,
            certification_values,
            industry_values,
        )
        return ParsedJobData(
            description_clean=description_clean,
            title_candidates=title.values,
            required_skills=required_skills,
            preferred_skills=preferred_skills,
            education_fields=education_fields,
            education_levels=education_levels,
            min_experience_years=experience.min_years,
            max_experience_years=experience.max_years,
            locations=location_values,
            languages=language_values,
            certifications=certification_values,
            industries=industry_values,
            keywords_tr=keywords_tr,
            keywords_en=keywords_en,
            requirements=requirements,
            parser_version=PARSER_VERSION,
            warnings=deduplicate_strings(warnings),
            confidence=confidence,
        )

    @staticmethod
    def _confidence(
        *,
        has_title: bool,
        has_skill: bool,
        has_experience: bool,
        has_education: bool,
        has_location: bool,
        has_language: bool,
        has_sections: bool,
    ) -> float:
        return round(
            (0.2 if has_title else 0)
            + (0.2 if has_skill else 0)
            + (0.15 if has_experience else 0)
            + (0.15 if has_education else 0)
            + (0.1 if has_location else 0)
            + (0.1 if has_language else 0)
            + (0.1 if has_sections else 0),
            2,
        )

    @staticmethod
    def _keywords(
        titles: tuple[str, ...],
        required_skills: tuple[str, ...],
        preferred_skills: tuple[str, ...],
        education_fields: tuple[str, ...],
        locations: tuple[str, ...],
        certifications: tuple[str, ...],
        industries: tuple[str, ...],
    ) -> tuple[tuple[str, ...], tuple[str, ...]]:
        english_titles = list(titles)
        turkish_titles = [
            variation for title in titles for variation in TITLE_VARIANTS_TR.get(title, ())
        ]
        common = [
            *required_skills,
            *preferred_skills,
            *education_fields,
            *(value.split(":", 1)[-1] for value in locations),
            *certifications,
            *industries,
        ]
        return (
            deduplicate_strings([*turkish_titles, *common], limit=30),
            deduplicate_strings([*english_titles, *common], limit=30),
        )
