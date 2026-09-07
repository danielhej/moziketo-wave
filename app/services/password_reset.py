from __future__ import annotations

import hashlib
import secrets

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.redis import connect_redis, get_redis
from app.core.security import hash_password
from app.models import User
from app.schemas.auth import ForgotPasswordResponse, ResetPasswordRequest


def _token_key(token: str) -> str:
    return f"reset:{hashlib.sha256(token.encode()).hexdigest()}"


def _expose_reset_token() -> bool:
    settings = get_settings()
    return settings.app_env != "production" or settings.debug


async def request_password_reset(
    session: AsyncSession, email: str
) -> ForgotPasswordResponse | None:
    user = await session.scalar(select(User).where(User.email == email.lower()))
    if user is None:
        return None

    settings = get_settings()
    token = secrets.token_urlsafe(32)
    await connect_redis()
    redis = get_redis()
    await redis.set(_token_key(token), str(user.id), ex=settings.password_reset_ttl_seconds)

    if not _expose_reset_token():
        return None

    return ForgotPasswordResponse(
        reset_token=token,
        expires_in=settings.password_reset_ttl_seconds,
    )


async def reset_password(session: AsyncSession, data: ResetPasswordRequest) -> None:
    await connect_redis()
    redis = get_redis()
    key = _token_key(data.token)
    user_id = await redis.get(key)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    from uuid import UUID

    try:
        uid = UUID(user_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        ) from exc

    user = await session.scalar(select(User).where(User.id == uid))
    if user is None:
        await redis.delete(key)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    user.password_hash = hash_password(data.new_password)
    await session.commit()
    await redis.delete(key)
