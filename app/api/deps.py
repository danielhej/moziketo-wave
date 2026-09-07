from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import safe_decode_token
from app.db.session import get_db
from app.models import User
from app.services.auth import get_user_by_id

DbSession = AsyncGenerator[AsyncSession, None]
get_db_session = get_db

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user_id(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> str:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = safe_decode_token(credentials.credentials)
    if payload is None or payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    return str(sub)


async def get_current_user(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> User:
    user = await get_user_by_id(session, user_id)
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account inactive")
    return user


__all__ = [
    "DbSession",
    "bearer_scheme",
    "get_current_user",
    "get_current_user_id",
    "get_db_session",
]
