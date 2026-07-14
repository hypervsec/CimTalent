from datetime import UTC

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.db.base import utc_now
from app.db.session import build_engine


async def test_engine_uses_configured_async_database_url() -> None:
    settings = Settings(
        app_env="test",
        database_url="postgresql+asyncpg://user:pass@localhost:5432/test_db",
        _env_file=None,
    )
    engine = build_engine(settings)

    try:
        assert engine.url.drivername == "postgresql+asyncpg"
        assert engine.url.database == "test_db"
        async with AsyncSession(engine) as session:
            assert session.is_active
    finally:
        await engine.dispose()


def test_utc_now_is_timezone_aware() -> None:
    assert utc_now().tzinfo is UTC
