from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.redis import connect_redis, get_redis
from app.models import User
from app.schemas.auth import VerifyEmailRequestResponse
from app.services.email import email_is_configured, send_email


def _token_key(token: str) -> str:
    return f"verify:{hashlib.sha256(token.encode()).hexdigest()}"


def _expose_verify_token() -> bool:
    settings = get_settings()
    return not email_is_configured() and (
        settings.app_env != "production" or settings.debug
    )


async def _store_token(token: str, user_id: str) -> int:
    settings = get_settings()
    await connect_redis()
    redis = get_redis()
    ttl = settings.email_verify_ttl_seconds
    await redis.set(_token_key(token), user_id, ex=ttl)
    return ttl


async def create_verification_token(user_id: str) -> tuple[str, int]:
    token = secrets.token_urlsafe(32)
    ttl = await _store_token(token, user_id)
    return token, ttl


async def send_verification_email(user: User) -> VerifyEmailRequestResponse | None:
    token, ttl = await create_verification_token(str(user.id))
    settings = get_settings()
    verify_url = f"{settings.frontend_verify_url.rstrip('/')}?token={token}"

    if email_is_configured():
        await send_email(
            to=user.email,
            subject="Verify your Moziketo account",
            body=(
                f"سلام {user.display_name},\n\n"
                f"برای تأیید ایمیل خود این لینک را باز کنید:\n{verify_url}\n\n"
                f"این لینک {ttl // 3600} ساعت اعتبار دارد."
            ),
        )
        return None

    if _expose_verify_token():
        return VerifyEmailRequestResponse(verify_token=token, expires_in=ttl)
    return None


async def confirm_verification_token(session: AsyncSession, token: str) -> None:
    await connect_redis()
    redis = get_redis()
    key = _token_key(token)
    user_id = await redis.get(key)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token",
        )

    try:
        uid = UUID(user_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token",
        ) from exc

    user = await session.scalar(select(User).where(User.id == uid))
    if user is None:
        await redis.delete(key)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token",
        )

    user.email_verified_at = datetime.now(UTC)
    await session.commit()
    await redis.delete(key)
