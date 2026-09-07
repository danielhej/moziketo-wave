from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db

DbSession = AsyncGenerator[AsyncSession, None]
get_db_session = get_db

__all__ = ["DbSession", "get_db_session"]
