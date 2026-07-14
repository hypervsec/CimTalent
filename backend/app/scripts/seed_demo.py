from __future__ import annotations

import asyncio
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import (
    CandidateProfileStatus,
    CandidateSkillSource,
    CandidateSource,
    JobSource,
    JobStatus,
    RequirementImportance,
    RequirementSource,
    RequirementType,
    SearchLanguage,
    SearchSource,
    SearchStatus,
    ShortlistStatus,
)
from app.db.models import (
    Candidate,
    CandidateCertification,
    CandidateEducation,
    CandidateExperience,
    CandidateLanguage,
    CandidateMatch,
    CandidateSkill,
    JobPosting,
    JobRequirement,
    SearchQuery,
    SearchResult,
    ShortlistEntry,
)
from app.db.session import async_session_factory


@dataclass(frozen=True, slots=True)
class SeedSummary:
    jobs: int
    requirements: int
    queries: int
    search_results: int
    candidates: int
    experiences: int
    educations: int
    skills: int
    certifications: int
    languages: int
    matches: int
    shortlist_entries: int


JOBS = (
    ("Software Developer", "Demo Industrial Systems", "Bursa"),
    ("Welding Engineer", "Example Manufacturing", "Gemlik"),
    ("Planning Engineer", "Sample Technology", "Kocaeli"),
)


async def seed_demo_data(session: AsyncSession) -> SeedSummary:
    jobs = []
    for title, company, city in JOBS:
        key = f"https://demo.local/jobs/{title.casefold().replace(' ', '-')}"
        job = await session.scalar(select(JobPosting).where(JobPosting.source_url == key))
        if job is None:
            job = JobPosting(
                source=JobSource.MANUAL,
                source_url=key,
                company_name=company,
                title=title,
                description_raw=f"Synthetic {title}",
                city=city,
                country="Türkiye",
                status=JobStatus.PARSED,
            )
            session.add(job)
            await session.flush()
        jobs.append(job)
        if not await session.scalar(
            select(JobRequirement.id).where(JobRequirement.job_id == job.id)
        ):
            session.add(
                JobRequirement(
                    job_id=job.id,
                    type=RequirementType.TITLE,
                    raw_value=title,
                    normalized_value=title.casefold(),
                    importance=RequirementImportance.REQUIRED,
                    weight=1,
                    confidence=1,
                    source=RequirementSource.MANUAL,
                )
            )
        for n in range(2):
            query = await session.scalar(
                select(SearchQuery).where(
                    SearchQuery.job_id == job.id, SearchQuery.normalized_query_key == f"demo-{n}"
                )
            )
            if query is None:
                query = SearchQuery(
                    job_id=job.id,
                    source=SearchSource.MANUAL,
                    language=SearchLanguage.EN,
                    query_text=f"{title} demo {n}",
                    normalized_query_key=f"demo-{n}",
                    status=SearchStatus.READY,
                )
                session.add(query)
                await session.flush()
            for rank in range(1, 4):
                url = f"https://www.linkedin.com/in/demo-{job.id.hex[:6]}-{n}-{rank}"
                if not await session.scalar(
                    select(SearchResult.id).where(
                        SearchResult.search_query_id == query.id, SearchResult.normalized_url == url
                    )
                ):
                    session.add(
                        SearchResult(
                            search_query_id=query.id,
                            source_url=url,
                            normalized_url=url,
                            title="Synthetic result",
                            result_rank=rank,
                        )
                    )
    for n in range(10):
        url = f"https://www.linkedin.com/in/demo-candidate-{n}"
        candidate = await session.scalar(
            select(Candidate).where(Candidate.normalized_profile_url == url)
        )
        if candidate is None:
            candidate = Candidate(
                primary_profile_url=url,
                normalized_profile_url=url,
                source=CandidateSource.DEMO,
                full_name=f"Demo Candidate {n}",
                headline="Software Engineer",
                city="Bursa" if n < 5 else "Kocaeli",
                country="Türkiye",
                current_title="Software Developer",
                profile_status=CandidateProfileStatus.SCRAPED,
                data_quality_score=70,
                total_experience_months=36,
            )
            session.add(candidate)
            await session.flush()
        if not await session.scalar(
            select(CandidateExperience.id).where(CandidateExperience.candidate_id == candidate.id)
        ):
            session.add(
                CandidateExperience(
                    candidate_id=candidate.id,
                    position_title_raw="Software Developer",
                    source="demo",
                    sort_order=0,
                    confidence=1,
                )
            )
        if not await session.scalar(
            select(CandidateEducation.id).where(CandidateEducation.candidate_id == candidate.id)
        ):
            session.add(
                CandidateEducation(
                    candidate_id=candidate.id,
                    institution_name="Demo University",
                    source="demo",
                    sort_order=0,
                    confidence=1,
                )
            )
        if not await session.scalar(
            select(CandidateSkill.id).where(CandidateSkill.candidate_id == candidate.id)
        ):
            session.add(
                CandidateSkill(
                    candidate_id=candidate.id,
                    raw_name="Python",
                    normalized_name="python",
                    source=CandidateSkillSource.MANUAL,
                    confidence=1,
                )
            )
        if not await session.scalar(
            select(CandidateLanguage.id).where(CandidateLanguage.candidate_id == candidate.id)
        ):
            session.add(
                CandidateLanguage(
                    candidate_id=candidate.id,
                    language="English",
                    language_normalized="english",
                    confidence=1,
                )
            )
        if not await session.scalar(
            select(CandidateCertification.id).where(
                CandidateCertification.candidate_id == candidate.id
            )
        ):
            session.add(
                CandidateCertification(
                    candidate_id=candidate.id, name="Demo Certificate", source="demo", confidence=1
                )
            )
        for job in jobs:
            if not await session.scalar(
                select(CandidateMatch.id).where(
                    CandidateMatch.job_id == job.id, CandidateMatch.candidate_id == candidate.id
                )
            ):
                session.add(
                    CandidateMatch(
                        job_id=job.id,
                        candidate_id=candidate.id,
                        total_score=70,
                        title_score=70,
                        skill_score=70,
                        experience_score=70,
                        industry_score=70,
                        education_score=70,
                        location_score=70,
                        language_score=70,
                        certification_score=70,
                        semantic_score=None,
                        score_version="demo-v1",
                    )
                )
        if n < 4 and not await session.scalar(
            select(ShortlistEntry.id).where(
                ShortlistEntry.job_id == jobs[0].id, ShortlistEntry.candidate_id == candidate.id
            )
        ):
            session.add(
                ShortlistEntry(
                    job_id=jobs[0].id, candidate_id=candidate.id, status=ShortlistStatus.SHORTLISTED
                )
            )
    await session.commit()
    models = (
        JobPosting,
        JobRequirement,
        SearchQuery,
        SearchResult,
        Candidate,
        CandidateExperience,
        CandidateEducation,
        CandidateSkill,
        CandidateCertification,
        CandidateLanguage,
        CandidateMatch,
        ShortlistEntry,
    )
    values = [int((await session.scalar(select(func.count(model.id)))) or 0) for model in models]
    return SeedSummary(*values)


async def main() -> None:
    async with async_session_factory() as session:
        print(await seed_demo_data(session))


if __name__ == "__main__":
    asyncio.run(main())
