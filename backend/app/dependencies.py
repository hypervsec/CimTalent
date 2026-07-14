from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.domain.matching.engine import RuleBasedMatchingEngine
from app.parsers.jobs.rule_based import RuleBasedJobParser
from app.repositories.candidate_enrichment import CandidateEnrichmentRepository
from app.repositories.candidate_matches import CandidateMatchRepository
from app.repositories.candidates import CandidateRepository
from app.repositories.enrichment_runs import EnrichmentRunRepository
from app.repositories.job_requirements import JobRequirementRepository
from app.repositories.jobs import JobRepository
from app.repositories.search_queries import SearchQueryRepository
from app.repositories.search_results import SearchResultRepository
from app.repositories.shortlists import ShortlistRepository
from app.services.candidate_discovery import CandidateDiscoveryService
from app.services.candidate_enrichment import CandidateEnrichmentService
from app.services.candidates import CandidateService
from app.services.job_parsing import JobParsingService
from app.services.jobs import JobService
from app.services.linkedin_enrichment import LinkedInCandidateEnrichmentService
from app.services.matching import CandidateMatchingService
from app.services.query_generation import QueryGenerationService
from app.services.search_result_import import SearchResultImportService
from app.services.shortlists import ShortlistService
from app.sourcing.manual_result_parser import ManualSearchResultParser
from app.sourcing.query_generator import GoogleXRayQueryGenerator

SessionDependency = Annotated[AsyncSession, Depends(get_db_session)]


def get_candidate_repository() -> CandidateRepository:
    return CandidateRepository()


CandidateRepositoryDependency = Annotated[CandidateRepository, Depends(get_candidate_repository)]


def get_candidate_service(repository: CandidateRepositoryDependency) -> CandidateService:
    return CandidateService(repository)


CandidateServiceDependency = Annotated[CandidateService, Depends(get_candidate_service)]


def get_candidate_enrichment_repository() -> CandidateEnrichmentRepository:
    return CandidateEnrichmentRepository()


CandidateEnrichmentRepositoryDependency = Annotated[
    CandidateEnrichmentRepository, Depends(get_candidate_enrichment_repository)
]


def get_enrichment_run_repository() -> EnrichmentRunRepository:
    return EnrichmentRunRepository()


EnrichmentRunRepositoryDependency = Annotated[
    EnrichmentRunRepository, Depends(get_enrichment_run_repository)
]


def get_candidate_enrichment_service(
    repository: CandidateEnrichmentRepositoryDependency,
    run_repository: EnrichmentRunRepositoryDependency,
) -> CandidateEnrichmentService:
    return CandidateEnrichmentService(repository, run_repository)


CandidateEnrichmentServiceDependency = Annotated[
    CandidateEnrichmentService, Depends(get_candidate_enrichment_service)
]


def get_linkedin_enrichment_service(
    enrichment_service: CandidateEnrichmentServiceDependency,
) -> LinkedInCandidateEnrichmentService:
    from app.config import get_settings

    return LinkedInCandidateEnrichmentService(enrichment_service, get_settings())


LinkedInEnrichmentServiceDependency = Annotated[
    LinkedInCandidateEnrichmentService, Depends(get_linkedin_enrichment_service)
]


def get_job_repository() -> JobRepository:
    return JobRepository()


JobRepositoryDependency = Annotated[JobRepository, Depends(get_job_repository)]


def get_job_requirement_repository() -> JobRequirementRepository:
    return JobRequirementRepository()


JobRequirementRepositoryDependency = Annotated[
    JobRequirementRepository, Depends(get_job_requirement_repository)
]


def get_job_parser() -> RuleBasedJobParser:
    return RuleBasedJobParser()


JobParserDependency = Annotated[RuleBasedJobParser, Depends(get_job_parser)]


def get_job_service(repository: JobRepositoryDependency) -> JobService:
    return JobService(repository)


JobServiceDependency = Annotated[JobService, Depends(get_job_service)]


def get_job_parsing_service(
    job_repository: JobRepositoryDependency,
    requirement_repository: JobRequirementRepositoryDependency,
    parser: JobParserDependency,
) -> JobParsingService:
    return JobParsingService(job_repository, requirement_repository, parser)


JobParsingServiceDependency = Annotated[JobParsingService, Depends(get_job_parsing_service)]


def get_search_query_repository() -> SearchQueryRepository:
    return SearchQueryRepository()


SearchQueryRepositoryDependency = Annotated[
    SearchQueryRepository, Depends(get_search_query_repository)
]


def get_query_generator() -> GoogleXRayQueryGenerator:
    return GoogleXRayQueryGenerator()


QueryGeneratorDependency = Annotated[GoogleXRayQueryGenerator, Depends(get_query_generator)]


def get_query_generation_service(
    job_repository: JobRepositoryDependency,
    requirement_repository: JobRequirementRepositoryDependency,
    query_repository: SearchQueryRepositoryDependency,
    generator: QueryGeneratorDependency,
) -> QueryGenerationService:
    return QueryGenerationService(
        job_repository, requirement_repository, query_repository, generator
    )


QueryGenerationServiceDependency = Annotated[
    QueryGenerationService, Depends(get_query_generation_service)
]


def get_search_result_repository() -> SearchResultRepository:
    return SearchResultRepository()


SearchResultRepositoryDependency = Annotated[
    SearchResultRepository, Depends(get_search_result_repository)
]


def get_candidate_discovery_service(
    candidate_repository: CandidateRepositoryDependency,
    result_repository: SearchResultRepositoryDependency,
    job_repository: JobRepositoryDependency,
) -> CandidateDiscoveryService:
    return CandidateDiscoveryService(candidate_repository, result_repository, job_repository)


CandidateDiscoveryServiceDependency = Annotated[
    CandidateDiscoveryService, Depends(get_candidate_discovery_service)
]


def get_manual_result_parser() -> ManualSearchResultParser:
    return ManualSearchResultParser()


ManualResultParserDependency = Annotated[
    ManualSearchResultParser, Depends(get_manual_result_parser)
]


def get_search_result_import_service(
    job_repository: JobRepositoryDependency,
    query_repository: SearchQueryRepositoryDependency,
    result_repository: SearchResultRepositoryDependency,
    parser: ManualResultParserDependency,
) -> SearchResultImportService:
    return SearchResultImportService(job_repository, query_repository, result_repository, parser)


SearchResultImportServiceDependency = Annotated[
    SearchResultImportService, Depends(get_search_result_import_service)
]


def get_candidate_match_repository() -> CandidateMatchRepository:
    return CandidateMatchRepository()


CandidateMatchRepositoryDependency = Annotated[
    CandidateMatchRepository, Depends(get_candidate_match_repository)
]


def get_matching_engine() -> RuleBasedMatchingEngine:
    return RuleBasedMatchingEngine()


def get_candidate_matching_service(
    repository: CandidateMatchRepositoryDependency,
) -> CandidateMatchingService:
    return CandidateMatchingService(repository, get_matching_engine())


CandidateMatchingServiceDependency = Annotated[
    CandidateMatchingService, Depends(get_candidate_matching_service)
]


def get_shortlist_repository() -> ShortlistRepository:
    return ShortlistRepository()


ShortlistRepositoryDependency = Annotated[ShortlistRepository, Depends(get_shortlist_repository)]


def get_shortlist_service(
    repository: ShortlistRepositoryDependency,
    match_repository: CandidateMatchRepositoryDependency,
) -> ShortlistService:
    return ShortlistService(repository, match_repository)


ShortlistServiceDependency = Annotated[ShortlistService, Depends(get_shortlist_service)]
