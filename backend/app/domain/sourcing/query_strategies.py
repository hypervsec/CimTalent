from dataclasses import dataclass

from app.domain.sourcing.types import QueryPrecision, QueryType


@dataclass(frozen=True, slots=True)
class QueryStrategy:
    query_type: QueryType
    precision: QueryPrecision
    expected_intent: str


TITLE_LOCATION = QueryStrategy(
    QueryType.TITLE_LOCATION, QueryPrecision.BALANCED, "title and location"
)
PRECISION = QueryStrategy(
    QueryType.PRECISION, QueryPrecision.STRICT, "strict title, skill and location"
)
TITLE_SKILLS = QueryStrategy(
    QueryType.TITLE_SKILLS, QueryPrecision.PRECISE, "title and required skills"
)
EDUCATION_LOCATION = QueryStrategy(
    QueryType.EDUCATION_LOCATION, QueryPrecision.BALANCED, "education and location"
)
INDUSTRY_TITLE = QueryStrategy(
    QueryType.INDUSTRY_TITLE, QueryPrecision.PRECISE, "industry and title"
)
REQUIRED_SKILLS = QueryStrategy(
    QueryType.REQUIRED_SKILLS, QueryPrecision.PRECISE, "required skill focus"
)
RECALL = QueryStrategy(QueryType.RECALL, QueryPrecision.BROAD_RECALL, "broad title recall")
