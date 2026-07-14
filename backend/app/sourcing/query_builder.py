import re

from app.domain.sourcing.constants import MAX_QUERY_LENGTH
from app.domain.sourcing.exceptions import QueryGenerationError
from app.domain.sourcing.normalizers import deduplicate_values, normalize_target_domain

QUOTE_RE = re.compile(r'["“”]+')
WHITESPACE_RE = re.compile(r"\s+")


class GoogleXRayQueryBuilder:
    def __init__(self, target_domain: str, max_length: int = MAX_QUERY_LENGTH) -> None:
        self.target_domain = normalize_target_domain(target_domain)
        self.max_length = max_length

    @staticmethod
    def quote(value: str) -> str:
        clean = WHITESPACE_RE.sub(" ", QUOTE_RE.sub(" ", value)).strip()
        return f'"{clean}"' if clean else ""

    @classmethod
    def group(cls, values: tuple[str, ...]) -> str:
        quoted = tuple(cls.quote(value) for value in deduplicate_values(values))
        quoted = tuple(value for value in quoted if value)
        if len(quoted) == 1:
            return quoted[0]
        return f"({' OR '.join(quoted)})" if quoted else ""

    def build(
        self,
        *,
        titles: tuple[str, ...],
        skills: tuple[str, ...] = (),
        locations: tuple[str, ...] = (),
        extras: tuple[str, ...] = (),
    ) -> str:
        title_group = self.group(titles)
        if not title_group:
            raise QueryGenerationError("At least one title is required.")
        required = [f"site:{self.target_domain}", title_group]
        optional = [self.group(skills), self.group(locations), self.group(extras)]
        optional = [part for part in optional if part]
        query = " ".join([*required, *optional])
        while len(query) > self.max_length and optional:
            optional.pop()
            query = " ".join([*required, *optional])
        if len(query) > self.max_length:
            available = self.max_length - len(required[0]) - 4
            raw_title = WHITESPACE_RE.sub(" ", QUOTE_RE.sub(" ", titles[0])).strip()
            if available < 1:
                raise QueryGenerationError("Query length limit is too low.")
            query = f'{required[0]} "{raw_title[:available]}"'
        return query.strip()
