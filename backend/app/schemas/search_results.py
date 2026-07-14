from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.sourcing.types import (
    ImportMode,
    ManualImportFormat,
    ManualResultInputData,
)
from app.schemas.common import UtcDateTime


class ManualResultInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str = Field(min_length=1, max_length=2048)
    title: str | None = Field(default=None, max_length=1000)
    snippet: str | None = None
    displayed_name: str | None = Field(default=None, max_length=255)
    displayed_headline: str | None = Field(default=None, max_length=1000)
    displayed_location: str | None = Field(default=None, max_length=500)
    rank: int | None = Field(default=None, ge=1)

    def to_domain(self) -> ManualResultInputData:
        return ManualResultInputData(
            url=self.url,
            title=self.title,
            snippet=self.snippet,
            displayed_name=self.displayed_name,
            displayed_headline=self.displayed_headline,
            displayed_location=self.displayed_location,
            rank=self.rank,
        )


class ImportSearchResultsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    format: ManualImportFormat
    mode: ImportMode = ImportMode.MERGE
    payload: str | list[str] | list[ManualResultInput]

    @model_validator(mode="after")
    def validate_payload_shape(self) -> Self:
        if self.format is ManualImportFormat.HTML and isinstance(self.payload, str):
            return self
        if (
            self.format is ManualImportFormat.URLS
            and isinstance(self.payload, list)
            and all(isinstance(item, str) for item in self.payload)
        ):
            return self
        if (
            self.format is ManualImportFormat.JSON
            and isinstance(self.payload, list)
            and all(isinstance(item, ManualResultInput) for item in self.payload)
        ):
            return self
        raise ValueError("Payload does not match the selected import format.")

    def domain_payload(
        self,
    ) -> str | tuple[str, ...] | tuple[ManualResultInputData, ...]:
        if isinstance(self.payload, str):
            return self.payload
        if all(isinstance(item, str) for item in self.payload):
            return tuple(item for item in self.payload if isinstance(item, str))
        return tuple(
            item.to_domain() for item in self.payload if isinstance(item, ManualResultInput)
        )


class SearchResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    search_query_id: UUID
    candidate_id: UUID | None
    source_url: str
    normalized_url: str
    source_domain: str | None
    title: str | None
    snippet: str | None
    displayed_name: str | None
    displayed_headline: str | None
    displayed_location: str | None
    result_rank: int | None
    is_duplicate: bool
    duplicate_of_id: UUID | None
    pre_score: float | None
    discovered_at: UtcDateTime
    created_at: UtcDateTime
    updated_at: UtcDateTime


class ImportSearchResultsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query_id: UUID
    mode: ImportMode
    received_count: int
    valid_count: int
    inserted_count: int
    duplicate_count: int
    invalid_count: int
    total_query_result_count: int
    warnings: tuple[str, ...]
    results: list[SearchResultRead]
