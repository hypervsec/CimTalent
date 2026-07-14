from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from app.db.enums import JobSource, JobStatus

if TYPE_CHECKING:
    from app.db.models import JobPosting


class JobSortField(StrEnum):
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"
    TITLE = "title"
    COMPANY_NAME = "company_name"
    STATUS = "status"


class SortDirection(StrEnum):
    ASC = "asc"
    DESC = "desc"


@dataclass(frozen=True, slots=True)
class JobListFilters:
    status: JobStatus | None = None
    source: JobSource | None = None
    city: str | None = None
    company_name: str | None = None
    title: str | None = None
    search: str | None = None
    created_from: datetime | None = None
    created_to: datetime | None = None


@dataclass(frozen=True, slots=True)
class JobSort:
    field: JobSortField = JobSortField.CREATED_AT
    direction: SortDirection = SortDirection.DESC


@dataclass(frozen=True, slots=True)
class JobWithCounts:
    job: JobPosting
    requirement_count: int = 0
    search_query_count: int = 0
    candidate_match_count: int = 0
    shortlist_count: int = 0


@dataclass(frozen=True, slots=True)
class PagedJobs:
    items: list[JobWithCounts]
    page: int
    page_size: int
    total_items: int

    @property
    def total_pages(self) -> int:
        if self.total_items == 0:
            return 0
        return (self.total_items + self.page_size - 1) // self.page_size

    @property
    def has_next(self) -> bool:
        return self.page < self.total_pages

    @property
    def has_previous(self) -> bool:
        return self.page > 1 and self.total_pages > 0
