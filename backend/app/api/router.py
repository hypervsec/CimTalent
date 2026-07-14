from fastapi import APIRouter

from app.api.v1.candidates import job_discovery_router as candidate_job_discovery_router
from app.api.v1.candidates import result_discovery_router as candidate_result_discovery_router
from app.api.v1.candidates import router as candidates_router
from app.api.v1.enrichment import router as enrichment_router
from app.api.v1.health import router as health_router
from app.api.v1.jobs import router as jobs_router
from app.api.v1.search_queries import job_router as search_query_job_router
from app.api.v1.search_queries import query_router as search_query_router
from app.api.v1.search_results import job_router as search_result_job_router
from app.api.v1.search_results import query_router as search_result_query_router
from app.api.v1.search_results import result_router as search_result_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(candidates_router, tags=["candidates"])
api_router.include_router(enrichment_router, tags=["candidate-enrichment"])
api_router.include_router(candidate_result_discovery_router, tags=["candidate-discovery"])
api_router.include_router(candidate_job_discovery_router, tags=["candidate-discovery"])
api_router.include_router(jobs_router, tags=["jobs"])
api_router.include_router(search_query_job_router, tags=["search-queries"])
api_router.include_router(search_query_router, tags=["search-queries"])
api_router.include_router(search_result_job_router, tags=["search-results"])
api_router.include_router(search_result_query_router, tags=["search-results"])
api_router.include_router(search_result_router, tags=["search-results"])
