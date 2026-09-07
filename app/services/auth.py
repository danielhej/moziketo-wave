
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.redis import get_redis
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    safe_decode_token,
    verify_password,
)
from app.models import User
from app.schemas.auth import (
    ChangePasswordRequest,
    RegisterRequest,
    RegisterResponse,
    SetPasswordRequest,
    TokenResponse,
    UpdateProfileRequest,
    UserResponse,
)
from app.services.email_verification import send_verification_email


def _user_response(user: User) -> UserResponse:
    providers = [account.provider for account in getattr(user, "oauth_accounts", [])]
    return UserResponse(
        id=str(user.id),
        email=user.email,
        display_name=user.display_name,
        is_active=user.is_active,
        email_verified=user.email_verified_at is not None,
        has_password=user.password_hash is not None,
        oauth_providers=providers,
        avatar_url=user.avatar_url,
    )


async def _load_user_with_oauth(session: AsyncSession, user_id: str) -> User:
    from uuid import UUID

    try:
        uid = UUID(user_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        ) from exc

    user = await session.scalar(
        select(User)
        .where(User.id == uid)
        .options(selectinload(User.oauth_accounts))
    )
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


async def register_user(session: AsyncSession, data: RegisterRequest) -> RegisterResponse:
    existing = await session.scalar(select(User).where(User.email == data.email.lower()))
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(
        email=data.email.lower(),
        password_hash=hash_password(data.password),
        display_name=data.display_name,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user, ["oauth_accounts"])

    verify = await send_verification_email(user)
    return RegisterResponse(
        user=_user_response(user),
        verify_token=verify.verify_token if verify else None,
        verify_expires_in=verify.expires_in if verify else None,
    )


async def login_user(session: AsyncSession, email: str, password: str) -> TokenResponse:
    user = await session.scalar(select(User).where(User.email == email.lower()))
    if user is None or user.password_hash is None or not verify_password(
        password, user.password_hash
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account inactive")

    return await issue_tokens(user)


async def issue_tokens(user: User) -> TokenResponse:
    settings = get_settings()
    subject = str(user.id)
    access = create_access_token(subject)
    refresh, jti = create_refresh_token(subject)
    from app.core.redis import connect_redis

    await connect_redis()
    redis = get_redis()
    ttl = settings.refresh_token_expire_days * 86400
    await redis.set(f"refresh:{jti}", subject, ex=ttl)
    return TokenResponse(access_token=access, refresh_token=refresh)


async def refresh_tokens(refresh_token: str) -> TokenResponse:
    payload = safe_decode_token(refresh_token)
    if payload is None or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    jti = payload.get("jti")
    sub = payload.get("sub")
    if not jti or not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    from app.core.redis import connect_redis

    await connect_redis()
    redis = get_redis()
    stored = await redis.get(f"refresh:{jti}")
    if stored != sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token revoked",
        )

    await redis.delete(f"refresh:{jti}")
    access = create_access_token(sub)
    new_refresh, new_jti = create_refresh_token(sub)
    settings = get_settings()
    ttl = settings.refresh_token_expire_days * 86400
    await redis.set(f"refresh:{new_jti}", sub, ex=ttl)
    return TokenResponse(access_token=access, refresh_token=new_refresh)


async def logout_user(refresh_token: str) -> None:
    payload = safe_decode_token(refresh_token)
    if payload and payload.get("jti"):
        from app.core.redis import connect_redis

        await connect_redis()
        redis = get_redis()
        await redis.delete(f"refresh:{payload['jti']}")


async def get_user_by_id(session: AsyncSession, user_id: str) -> User:
    return await _load_user_with_oauth(session, user_id)


async def get_current_user_response(session: AsyncSession, user_id: str) -> UserResponse:
    user = await _load_user_with_oauth(session, user_id)
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account inactive")
    return _user_response(user)


async def update_profile(
    session: AsyncSession, user_id: str, data: UpdateProfileRequest
) -> UserResponse:
    user = await _load_user_with_oauth(session, user_id)
    if data.display_name is not None:
        user.display_name = data.display_name
    if "avatar_url" in data.model_fields_set:
        user.avatar_url = data.avatar_url
    await session.commit()
    await session.refresh(user, ["oauth_accounts"])
    return _user_response(user)


async def change_password(
    session: AsyncSession, user_id: str, data: ChangePasswordRequest
) -> None:
    from uuid import UUID

    try:
        uid = UUID(user_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        ) from exc

    user = await session.scalar(select(User).where(User.id == uid))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    if user.password_hash is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OAuth-only account — use set-password first",
        )
    if not verify_password(data.current_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )
    user.password_hash = hash_password(data.new_password)
    await session.commit()


async def set_password(session: AsyncSession, user_id: str, data: SetPasswordRequest) -> None:
    from uuid import UUID

    try:
        uid = UUID(user_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        ) from exc

    user = await session.scalar(select(User).where(User.id == uid))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    if user.password_hash is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Password already set — use change-password",
        )
    user.password_hash = hash_password(data.new_password)
    await session.commit()
