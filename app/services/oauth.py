from __future__ import annotations

import secrets
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import httpx
from authlib.integrations.httpx_client import AsyncOAuth2Client
from fastapi import HTTPException, status
from jose import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.redis import connect_redis, get_redis
from app.models import OAuthAccount, OAuthProvider, User
from app.schemas.auth import TokenResponse
from app.services.auth import issue_tokens

OAUTH_STATE_TTL = 600
OAUTH_CODE_TTL = 60


@dataclass
class OAuthProfile:
    provider_user_id: str
    email: str
    display_name: str


def _ensure_provider_allowed(settings: Settings, provider: str) -> None:
    if provider == OAuthProvider.APPLE and not settings.oauth_apple_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Apple Sign In is disabled",
        )
    if provider not in OAuthProvider.ENABLED:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown OAuth provider")


def _provider_config(settings: Settings, provider: str) -> dict[str, Any]:
    _ensure_provider_allowed(settings, provider)
    if provider == OAuthProvider.GOOGLE:
        if not settings.google_client_id or not settings.google_client_secret:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Google OAuth is not configured",
            )
        return {
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
            "token_url": "https://oauth2.googleapis.com/token",
            "userinfo_url": "https://openidconnect.googleapis.com/v1/userinfo",
            "scope": "openid email profile",
        }
    if provider == OAuthProvider.GITHUB:
        if not settings.github_client_id or not settings.github_client_secret:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="GitHub OAuth is not configured",
            )
        return {
            "client_id": settings.github_client_id,
            "client_secret": settings.github_client_secret,
            "authorize_url": "https://github.com/login/oauth/authorize",
            "token_url": "https://github.com/login/oauth/access_token",
            "userinfo_url": "https://api.github.com/user",
            "scope": "read:user user:email",
        }
    if provider == OAuthProvider.APPLE:
        if not all(
            [
                settings.apple_client_id,
                settings.apple_team_id,
                settings.apple_key_id,
                settings.apple_private_key,
            ]
        ):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Apple OAuth is not configured",
            )
        return {
            "client_id": settings.apple_client_id,
            "client_secret": _apple_client_secret(settings),
            "authorize_url": "https://appleid.apple.com/auth/authorize",
            "token_url": "https://appleid.apple.com/auth/token",
            "scope": "name email",
        }
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown OAuth provider")


def _apple_client_secret(settings: Settings) -> str:
    now = int(time.time())
    headers = {"kid": settings.apple_key_id, "alg": "ES256"}
    payload = {
        "iss": settings.apple_team_id,
        "iat": now,
        "exp": now + 3600,
        "aud": "https://appleid.apple.com",
        "sub": settings.apple_client_id,
    }
    private_key = settings.apple_private_key.replace("\\n", "\n")
    return jwt.encode(payload, private_key, algorithm="ES256", headers=headers)


def _callback_url(settings: Settings, provider: str) -> str:
    base = settings.oauth_api_base_url.rstrip("/")
    return f"{base}/auth/oauth/{provider}/callback"


async def _store_state(state: str, provider: str) -> None:
    await connect_redis()
    redis = get_redis()
    await redis.set(f"oauth_state:{state}", provider, ex=OAUTH_STATE_TTL)


async def _pop_state(state: str) -> str | None:
    await connect_redis()
    redis = get_redis()
    key = f"oauth_state:{state}"
    provider = await redis.get(key)
    if provider:
        await redis.delete(key)
    return provider


async def _store_oauth_code(code: str, user_id: str) -> None:
    await connect_redis()
    redis = get_redis()
    await redis.set(f"oauth_code:{code}", user_id, ex=OAUTH_CODE_TTL)


async def _pop_oauth_code(code: str) -> str | None:
    await connect_redis()
    redis = get_redis()
    key = f"oauth_code:{code}"
    user_id = await redis.get(key)
    if user_id:
        await redis.delete(key)
    return user_id


async def build_authorize_redirect(provider: str) -> str:
    settings = get_settings()
    _ensure_provider_allowed(settings, provider)
    cfg = _provider_config(settings, provider)
    state = secrets.token_urlsafe(32)
    await _store_state(state, provider)

    client = AsyncOAuth2Client(
        client_id=cfg["client_id"],
        client_secret=cfg.get("client_secret"),
        scope=cfg.get("scope"),
        redirect_uri=_callback_url(settings, provider),
    )
    uri, _ = client.create_authorization_url(
        cfg["authorize_url"],
        state=state,
        response_mode="query",
    )
    return uri


async def _fetch_google_profile(token: dict[str, Any], cfg: dict[str, Any]) -> OAuthProfile:
    async with httpx.AsyncClient() as http:
        resp = await http.get(
            cfg["userinfo_url"],
            headers={"Authorization": f"Bearer {token['access_token']}"},
        )
        resp.raise_for_status()
        data = resp.json()
    email = data.get("email")
    if not email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email not provided")
    return OAuthProfile(
        provider_user_id=str(data["sub"]),
        email=email.lower(),
        display_name=data.get("name") or email.split("@")[0],
    )


async def _fetch_github_profile(token: dict[str, Any], cfg: dict[str, Any]) -> OAuthProfile:
    headers = {
        "Authorization": f"Bearer {token['access_token']}",
        "Accept": "application/vnd.github+json",
    }
    async with httpx.AsyncClient() as http:
        user_resp = await http.get(cfg["userinfo_url"], headers=headers)
        user_resp.raise_for_status()
        user_data = user_resp.json()
        email = user_data.get("email")
        if not email:
            emails_resp = await http.get("https://api.github.com/user/emails", headers=headers)
            emails_resp.raise_for_status()
            emails = emails_resp.json()
            primary = next((e for e in emails if e.get("primary")), None)
            email = primary["email"] if primary else (emails[0]["email"] if emails else None)
    if not email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email not provided")
    return OAuthProfile(
        provider_user_id=str(user_data["id"]),
        email=email.lower(),
        display_name=user_data.get("name") or user_data.get("login") or email.split("@")[0],
    )


async def _fetch_apple_profile(token: dict[str, Any]) -> OAuthProfile:
    id_token = token.get("id_token")
    if not id_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Apple id_token missing",
        )
    claims = jwt.get_unverified_claims(id_token)
    email = claims.get("email")
    sub = claims.get("sub")
    if not sub:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Apple sub missing")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email not provided by Apple",
        )
    return OAuthProfile(
        provider_user_id=str(sub),
        email=email.lower(),
        display_name=email.split("@")[0],
    )


async def _fetch_profile(
    provider: str, token: dict[str, Any], cfg: dict[str, Any]
) -> OAuthProfile:
    if provider == OAuthProvider.GOOGLE:
        return await _fetch_google_profile(token, cfg)
    if provider == OAuthProvider.GITHUB:
        return await _fetch_github_profile(token, cfg)
    return await _fetch_apple_profile(token)


async def _upsert_oauth_user(
    session: AsyncSession, provider: str, profile: OAuthProfile
) -> User:
    existing_oauth = await session.scalar(
        select(OAuthAccount).where(
            OAuthAccount.provider == provider,
            OAuthAccount.provider_user_id == profile.provider_user_id,
        )
    )
    if existing_oauth is not None:
        user = await session.scalar(select(User).where(User.id == existing_oauth.user_id))
        if user is None:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return user

    user = await session.scalar(select(User).where(User.email == profile.email))
    if user is None:
        user = User(
            email=profile.email,
            password_hash=None,
            display_name=profile.display_name,
        )
        session.add(user)
        await session.flush()
    elif not user.display_name and profile.display_name:
        user.display_name = profile.display_name

    if user.email_verified_at is None:
        user.email_verified_at = datetime.now(UTC)

    existing_for_user = await session.scalar(
        select(OAuthAccount).where(
            OAuthAccount.user_id == user.id,
            OAuthAccount.provider == provider,
        )
    )
    if existing_for_user is None:
        session.add(
            OAuthAccount(
                user_id=user.id,
                provider=provider,
                provider_user_id=profile.provider_user_id,
                email_at_link=profile.email,
            )
        )
    else:
        existing_for_user.provider_user_id = profile.provider_user_id
        existing_for_user.email_at_link = profile.email
    await session.commit()
    await session.refresh(user)
    return user


async def handle_oauth_callback(
    session: AsyncSession, provider: str, *, code: str, state: str
) -> str:
    settings = get_settings()
    _ensure_provider_allowed(settings, provider)
    stored_provider = await _pop_state(state)
    if stored_provider != provider:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OAuth state")

    cfg = _provider_config(settings, provider)
    client = AsyncOAuth2Client(
        client_id=cfg["client_id"],
        client_secret=cfg.get("client_secret"),
        redirect_uri=_callback_url(settings, provider),
    )
    token = await client.fetch_token(
        cfg["token_url"],
        code=code,
        grant_type="authorization_code",
    )
    profile = await _fetch_profile(provider, token, cfg)
    user = await _upsert_oauth_user(session, provider, profile)

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account inactive")

    exchange_code = secrets.token_urlsafe(32)
    await _store_oauth_code(exchange_code, str(user.id))
    return exchange_code


def frontend_callback_url(exchange_code: str) -> str:
    settings = get_settings()
    base = settings.oauth_frontend_callback_url.rstrip("/")
    return f"{base}?code={exchange_code}"


async def exchange_oauth_code(session: AsyncSession, code: str) -> TokenResponse:
    user_id = await _pop_oauth_code(code)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired OAuth code",
        )

    try:
        uid = UUID(user_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired OAuth code",
        ) from exc

    user = await session.scalar(select(User).where(User.id == uid))
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired OAuth code",
        )

    return await issue_tokens(user)
