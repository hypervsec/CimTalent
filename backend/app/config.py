from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False
    )

    app_name: str = "CimTalent AI"
    app_env: Literal["development", "test", "production"] = "development"
    debug: bool = False
    api_prefix: str = "/api/v1"
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/cimtalent"
    redis_url: str = "redis://localhost:6379/0"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])
    debug_artifact_retention_days: int = 7

    enable_linkedin_people_search: bool = False
    enable_google_api_search: bool = False
    enable_ai_provider: bool = False

    browser_headless: bool = True
    browser_timeout_ms: int = Field(default=30_000, gt=0)
    browser_navigation_timeout_ms: int = Field(default=45_000, gt=0)
    browser_viewport_width: int = Field(default=1440, ge=320, le=7680)
    browser_viewport_height: int = Field(default=900, ge=240, le=4320)
    browser_slow_mo_ms: int = Field(default=0, ge=0, le=60_000)
    browser_user_agent: str = ""
    linkedin_session_file: Path = Path(".sessions/linkedin.json")
    browser_artifact_dir: Path = Path(".artifacts/browser")
    browser_save_screenshot_on_error: bool = True
    browser_save_html_on_error: bool = False
    browser_artifact_retention_days: int = Field(default=3, ge=0, le=365)
    linkedin_base_url: str = "https://www.linkedin.com"
    linkedin_login_timeout_seconds: int = Field(default=300, gt=0, le=3600)
    enrichment_max_request_bytes: int = Field(default=2_000_000, ge=1_024, le=20_000_000)

    @field_validator("linkedin_session_file")
    @classmethod
    def validate_session_path(cls, value: Path) -> Path:
        if ".." in value.parts:
            raise ValueError("Session path traversal is not allowed.")
        if not value.is_absolute() and (not value.parts or value.parts[0] != ".sessions"):
            raise ValueError("Relative session files must be inside .sessions.")
        return value

    @field_validator("browser_artifact_dir")
    @classmethod
    def validate_artifact_path(cls, value: Path) -> Path:
        if ".." in value.parts:
            raise ValueError("Artifact path traversal is not allowed.")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
