from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.enrichment.enums import (
    EnrichmentImportMode,
    EnrichmentMode,
    EnrichmentSection,
    IdentityUpdateStrategy,
)
from app.domain.linkedin.enums import LinkedInProviderMode


class LinkedInEnrichmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: EnrichmentMode = EnrichmentMode.FAST
    import_mode: EnrichmentImportMode = EnrichmentImportMode.MERGE
    identity_update_strategy: IdentityUpdateStrategy = IdentityUpdateStrategy.FILL_EMPTY
    requested_sections: list[EnrichmentSection] | None = None
    provider_mode: LinkedInProviderMode = LinkedInProviderMode.FIXTURE
    fixture_key: str | None = Field(default=None, max_length=120)
    parser_version_override: str | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def validate_provider_request(self) -> "LinkedInEnrichmentRequest":
        if self.provider_mode is LinkedInProviderMode.LIVE and self.fixture_key:
            raise ValueError("fixture_key is only valid for fixture provider mode")
        if self.provider_mode is LinkedInProviderMode.FIXTURE and not self.fixture_key:
            raise ValueError("fixture_key is required for fixture provider mode")
        if self.fixture_key and (
            ".." in self.fixture_key or "/" in self.fixture_key or "\\" in self.fixture_key
        ):
            raise ValueError("fixture_key contains an unsafe path")
        if self.requested_sections is not None:
            self.requested_sections = list(dict.fromkeys(self.requested_sections))
        return self
