import pytest
from pydantic import ValidationError

from app.config import Settings


def test_settings_have_safe_feature_defaults() -> None:
    settings = Settings(app_env="test", _env_file=None)

    assert settings.app_name == "CimTalent AI"
    assert settings.api_prefix == "/api/v1"
    assert settings.enable_linkedin_people_search is False
    assert settings.enable_google_api_search is False
    assert settings.enable_ai_provider is False
    assert settings.browser_headless is True
    assert settings.browser_save_html_on_error is False
    assert settings.linkedin_session_file.as_posix() == ".sessions/linkedin.json"


def test_browser_settings_reject_unsafe_values() -> None:
    with pytest.raises(ValidationError):
        Settings(app_env="test", browser_timeout_ms=0, _env_file=None)
    with pytest.raises(ValidationError):
        Settings(app_env="test", linkedin_session_file="../secret.json", _env_file=None)
    with pytest.raises(ValidationError):
        Settings(app_env="test", linkedin_session_file="session.json", _env_file=None)
