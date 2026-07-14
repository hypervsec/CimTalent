from collections.abc import AsyncIterator
from uuid import UUID, uuid4

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.enums import JobSource, JobStatus, SearchLanguage, SearchSource, SearchStatus
from app.db.models import SearchQuery, SearchResult
from app.domain.jobs import JobNotFoundError
from app.domain.sourcing import (
    ManualImportPayloadTooLargeError,
    ManualImportValidationError,
    SearchQueryNotFoundError,
    SearchResultNotFoundError,
    SearchResultPersistenceError,
)
from app.domain.sourcing.types import (
    ImportMode,
    ManualImportFormat,
    ManualResultInputData,
    ParsedManualSearchResult,
    SearchResultFilters,
    SearchResultSort,
)
from app.repositories.jobs import JobRepository
from app.repositories.search_queries import SearchQueryRepository
from app.repositories.search_results import SearchResultRepository
from app.services.search_result_import import SearchResultImportService
from app.sourcing.manual_result_parser import MAX_HTML_BYTES, ManualSearchResultParser


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with AsyncSession(engine, expire_on_commit=False) as database_session:
        yield database_session
    await engine.dispose()


def service(repository: SearchResultRepository | None = None) -> SearchResultImportService:
    return SearchResultImportService(
        JobRepository(),
        SearchQueryRepository(),
        repository or SearchResultRepository(),
        ManualSearchResultParser(),
    )


async def create_query(session: AsyncSession, suffix: str = "one") -> SearchQuery:
    job = await JobRepository().create(
        session,
        data={
            "source": JobSource.MANUAL,
            "company_name": f"Example {suffix}",
            "title": "Developer",
            "description_raw": "Description",
            "status": JobStatus.PARSED,
        },
    )
    query = SearchQuery(
        job_id=job.id,
        source=SearchSource.MANUAL,
        language=SearchLanguage.EN,
        query_text=f"query {suffix}",
        normalized_query_key=f"query {suffix}",
        status=SearchStatus.READY,
    )
    session.add(query)
    await session.commit()
    return query


async def test_json_merge_is_idempotent_and_updates_query(session: AsyncSession) -> None:
    query = await create_query(session)
    payload = (
        ManualResultInputData("https://linkedin.com/in/demo?trk=x", "Demo - Engineer"),
        ManualResultInputData("https://github.com/demo"),
    )

    first = await service().import_results(
        session,
        query.id,
        import_format=ManualImportFormat.JSON,
        mode=ImportMode.MERGE,
        payload=payload,
    )
    second = await service().import_results(
        session,
        query.id,
        import_format=ManualImportFormat.JSON,
        mode=ImportMode.MERGE,
        payload=payload,
    )
    await session.refresh(query)

    assert first.inserted_count == 2
    assert second.inserted_count == 0
    assert second.duplicate_count == 2
    assert query.result_count == 2
    assert query.status is SearchStatus.COMPLETED
    assert query.executed_at is not None


async def test_urls_html_replace_and_listing(session: AsyncSession) -> None:
    query = await create_query(session)
    importer = service()
    await importer.import_results(
        session,
        query.id,
        import_format=ManualImportFormat.URLS,
        mode=ImportMode.MERGE,
        payload=("https://example.com/old",),
    )
    replaced = await importer.import_results(
        session,
        query.id,
        import_format=ManualImportFormat.HTML,
        mode=ImportMode.REPLACE,
        payload='<article><a href="https://example.com/new">New Result</a></article>',
    )
    query_list = await importer.list_for_query(
        session,
        query.id,
        page=1,
        page_size=10,
        filters=SearchResultFilters(),
        sort=SearchResultSort(),
    )
    job_list = await importer.list_for_job(
        session,
        query.job_id,
        page=1,
        page_size=10,
        filters=SearchResultFilters(),
        sort=SearchResultSort(),
    )

    assert replaced.inserted_count == 1
    assert replaced.total_query_result_count == 1
    assert query_list.total_items == job_list.total_items == 1
    assert query_list.items[0].normalized_url == "https://example.com/new"


async def test_cross_query_duplicate_is_marked(session: AsyncSession) -> None:
    first_query = await create_query(session, "first")
    second_query = await create_query(session, "second")
    importer = service()
    payload = ("https://linkedin.com/in/same-profile",)
    await importer.import_results(
        session,
        first_query.id,
        import_format=ManualImportFormat.URLS,
        mode=ImportMode.MERGE,
        payload=payload,
    )
    outcome = await importer.import_results(
        session,
        second_query.id,
        import_format=ManualImportFormat.URLS,
        mode=ImportMode.MERGE,
        payload=payload,
    )

    assert outcome.duplicate_count == 1
    assert outcome.results[0].is_duplicate is True
    assert outcome.results[0].duplicate_of_id is not None


async def test_missing_and_oversized_payload(session: AsyncSession) -> None:
    query = await create_query(session)
    with pytest.raises(SearchQueryNotFoundError):
        await service().import_results(
            session,
            uuid4(),
            import_format=ManualImportFormat.URLS,
            mode=ImportMode.MERGE,
            payload=(),
        )
    with pytest.raises(ManualImportPayloadTooLargeError):
        await service().import_results(
            session,
            query.id,
            import_format=ManualImportFormat.HTML,
            mode=ImportMode.MERGE,
            payload="x" * (MAX_HTML_BYTES + 1),
        )


class FailingResultRepository(SearchResultRepository):
    async def create_many(
        self,
        session: AsyncSession,
        *,
        query_id: UUID,
        results: tuple[ParsedManualSearchResult, ...],
        canonical: dict[str, SearchResult],
    ) -> list[SearchResult]:
        raise SQLAlchemyError("failure")


async def test_replace_persistence_failure_rolls_back(session: AsyncSession) -> None:
    query = await create_query(session)
    query_id = query.id
    await service().import_results(
        session,
        query_id,
        import_format=ManualImportFormat.URLS,
        mode=ImportMode.MERGE,
        payload=("https://example.com/old",),
    )

    with pytest.raises(SearchResultPersistenceError):
        await service(FailingResultRepository()).import_results(
            session,
            query_id,
            import_format=ManualImportFormat.URLS,
            mode=ImportMode.REPLACE,
            payload=("https://example.com/new",),
        )

    assert (
        await SearchResultRepository().count_by_query(
            session, query_id=query_id, filters=SearchResultFilters()
        )
        == 1
    )


async def test_missing_lists_get_and_invalid_shape(session: AsyncSession) -> None:
    importer = service()
    with pytest.raises(SearchQueryNotFoundError):
        await importer.list_for_query(
            session,
            uuid4(),
            page=1,
            page_size=10,
            filters=SearchResultFilters(),
            sort=SearchResultSort(),
        )
    with pytest.raises(JobNotFoundError):
        await importer.list_for_job(
            session,
            uuid4(),
            page=1,
            page_size=10,
            filters=SearchResultFilters(),
            sort=SearchResultSort(),
        )
    with pytest.raises(SearchResultNotFoundError):
        await importer.get(session, uuid4())
    query = await create_query(session, "invalid-shape")
    with pytest.raises(ManualImportValidationError):
        await importer.import_results(
            session,
            query.id,
            import_format=ManualImportFormat.JSON,
            mode=ImportMode.MERGE,
            payload=("not-json-records",),
        )
