from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import Candidate, CandidateExperience, JobPosting
from app.scripts.seed_demo import seed_demo_data


async def test_seed_is_idempotent_and_restores_children() -> None:
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        first = await seed_demo_data(session)
        assert first.jobs >= 3 and first.candidates >= 10 and first.search_results >= 15
        assert (
            min(
                first.requirements,
                first.queries,
                first.experiences,
                first.skills,
                first.matches,
                first.shortlist_entries,
            )
            > 0
        )
        baseline = (first.jobs, first.candidates, first.search_results, first.matches)
        experience = await session.scalar(select(CandidateExperience))
        assert experience is not None
        await session.delete(experience)
        await session.commit()
        second = await seed_demo_data(session)
        assert (second.jobs, second.candidates, second.search_results, second.matches) == baseline
        assert int((await session.scalar(select(func.count(CandidateExperience.id)))) or 0) >= 10
        assert (
            int((await session.scalar(select(func.count(Candidate.normalized_profile_url)))) or 0)
            == second.candidates
        )
        assert int((await session.scalar(select(func.count(JobPosting.id)))) or 0) == second.jobs
    await engine.dispose()
