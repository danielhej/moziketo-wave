from __future__ import annotations

import hashlib
import json
import secrets
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.redis import connect_redis, get_redis
from app.core.security import verify_password
from app.models import Favorite, PlayEvent, Playlist, PlaylistTrack, User
from app.models.webhook import WebhookEvent
from app.schemas.auth import UserExportResponse
from app.services.email import email_is_configured, send_email
from app.services.webhooks import emit_event


def _change_email_key(token: str) -> str:
    return f"change_email:{hashlib.sha256(token.encode()).hexdigest()}"


def _expose_change_email_token() -> bool:
    settings = get_settings()
    return not email_is_configured() and (
        settings.app_env != "production" or settings.debug
    )


async def request_change_email(
    session: AsyncSession, user: User, new_email: str
) -> dict[str, Any] | None:
    new_email = new_email.lower().strip()
    if new_email == user.email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email unchanged")

    existing = await session.scalar(select(User).where(User.email == new_email))
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already in use")

    token = secrets.token_urlsafe(32)
    settings = get_settings()
    await connect_redis()
    redis = get_redis()
    ttl = settings.email_change_ttl_seconds
    payload = json.dumps({"user_id": str(user.id), "new_email": new_email})
    await redis.set(_change_email_key(token), payload, ex=ttl)

    confirm_url = f"{settings.frontend_change_email_url.rstrip('/')}?token={token}"
    if email_is_configured():
        await send_email(
            to=new_email,
            subject="Confirm your new Moziketo email",
            body=(
                f"سلام {user.display_name},\n\n"
                f"برای تأیید ایمیل جدید این لینک را باز کنید:\n{confirm_url}\n\n"
                f"این لینک {ttl // 3600} ساعت اعتبار دارد."
            ),
        )
        user.pending_email = new_email
        user.email_change_token_hash = hashlib.sha256(token.encode()).hexdigest()
        await session.commit()
        return None

    if _expose_change_email_token():
        user.pending_email = new_email
        user.email_change_token_hash = hashlib.sha256(token.encode()).hexdigest()
        await session.commit()
        return {"change_email_token": token, "expires_in": ttl}
    return None


async def confirm_change_email(session: AsyncSession, token: str) -> None:
    await connect_redis()
    redis = get_redis()
    key = _change_email_key(token)
    raw = await redis.get(key)
    if raw is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired token"
        )

    data = json.loads(raw)
    uid = UUID(data["user_id"])
    new_email = data["new_email"]
    user = await session.scalar(select(User).where(User.id == uid))
    if user is None:
        await redis.delete(key)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired token"
        )

    conflict = await session.scalar(select(User).where(User.email == new_email, User.id != uid))
    if conflict is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already in use")

    user.email = new_email
    user.pending_email = None
    user.email_change_token_hash = None
    user.email_verified_at = datetime.now(UTC)
    await session.commit()
    await redis.delete(key)


async def export_user_data(session: AsyncSession, user: User) -> UserExportResponse:
    favorites = await session.scalars(
        select(Favorite)
        .options(selectinload(Favorite.track))
        .where(Favorite.user_id == user.id)
    )
    playlists = await session.scalars(
        select(Playlist)
        .options(selectinload(Playlist.playlist_tracks).selectinload(PlaylistTrack.track))
        .where(Playlist.user_id == user.id)
    )
    history = await session.scalars(
        select(PlayEvent)
        .options(selectinload(PlayEvent.track))
        .where(PlayEvent.user_id == user.id)
        .order_by(PlayEvent.played_at.desc())
        .limit(500)
    )
    return UserExportResponse(
        profile={
            "id": str(user.id),
            "email": user.email,
            "display_name": user.display_name,
            "avatar_url": user.avatar_url,
            "created_at": user.created_at.isoformat(),
            "email_verified": user.email_verified_at is not None,
        },
        favorites=[f.track.slug for f in favorites if f.track],
        playlists=[
            {
                "slug": p.slug,
                "title": p.title,
                "tracks": [pt.track.slug for pt in p.playlist_tracks if pt.track],
            }
            for p in playlists
        ],
        play_history=[
            {"track_slug": e.track.slug, "played_at": e.played_at.isoformat()}
            for e in history
            if e.track
        ],
    )


async def delete_account(
    session: AsyncSession,
    user: User,
    *,
    password: str | None = None,
    confirm: bool = False,
) -> None:
    if not confirm:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="confirm=true required")

    if user.password_hash is not None:
        if not password or not verify_password(password, user.password_hash):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid password")

    user_id = str(user.id)
    user.deleted_at = datetime.now(UTC)
    user.is_active = False
    user.email = f"deleted+{user.id}@moziketo.invalid"
    user.display_name = "Deleted User"
    user.password_hash = None
    user.avatar_url = None
    user.pending_email = None
    user.email_change_token_hash = None
    await session.commit()

    await emit_event(session, WebhookEvent.USER_DELETED, {"user_id": user_id})
