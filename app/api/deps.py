from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import safe_decode_token
from app.db.session import get_db
from app.models import User
from app.services.auth import get_user_by_id
from app.services.rate_limit import check_rate_limit, client_ip

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
    if user.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account deleted")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account inactive")
    return user


async def rate_limit_search(request: Request) -> None:
    from app.core.config import get_settings

    settings = get_settings()
    if not settings.public_rate_limit_enabled:
        return
    await check_rate_limit(
        "search",
        client_ip(request),
        limit=settings.public_search_ip_limit,
        window_seconds=settings.public_search_ip_window,
    )


async def rate_limit_playback(request: Request) -> None:
    from app.core.config import get_settings

    settings = get_settings()
    if not settings.public_rate_limit_enabled:
        return
    await check_rate_limit(
        "playback",
        client_ip(request),
        limit=settings.public_playback_ip_limit,
        window_seconds=settings.public_playback_ip_window,
    )


async def rate_limit_catalog(request: Request) -> None:
    from app.core.config import get_settings

    settings = get_settings()
    if not settings.public_rate_limit_enabled:
        return
    await check_rate_limit(
        "catalog",
        client_ip(request),
        limit=settings.public_catalog_ip_limit,
        window_seconds=settings.public_catalog_ip_window,
    )


__all__ = [
    "DbSession",
    "bearer_scheme",
    "get_current_user",
    "get_current_user_id",
    "get_db_session",
    "rate_limit_catalog",
    "rate_limit_playback",
    "rate_limit_search",
]
