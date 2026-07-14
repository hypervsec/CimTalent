from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base


class BaseRepository[ModelT: Base]:
    def __init__(self, model: type[ModelT]) -> None:
        self.model = model

    async def get_by_id(self, session: AsyncSession, entity_id: UUID) -> ModelT | None:
        return await session.get(self.model, entity_id)
