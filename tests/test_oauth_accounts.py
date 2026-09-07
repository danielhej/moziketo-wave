import uuid

from httpx import AsyncClient

from app.core.redis import connect_redis, get_redis
from app.models import OAuthAccount, OAuthProvider


async def test_list_oauth_accounts_empty(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    response = await client.get("/api/v1/auth/me/oauth", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == []


async def test_unlink_last_method_blocked(client: AsyncClient, test_engine) -> None:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    email = f"oauthonly-{uuid.uuid4().hex[:8]}@moziketo.ir"
    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "securepass1", "display_name": "OAuth Test"},
    )
    user_id = reg.json()["user"]["id"]

    session_factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    provider_user_id = f"gh-{uuid.uuid4().hex[:8]}"
    async with session_factory() as session:
        from uuid import UUID

        from app.models import User

        user = await session.get(User, UUID(user_id))
        assert user is not None
        user.password_hash = None
        session.add(
            OAuthAccount(
                user_id=user.id,
                provider=OAuthProvider.GITHUB,
                provider_user_id=provider_user_id,
                email_at_link=email,
            )
        )
        await session.commit()

    await connect_redis()
    redis = get_redis()
    code = f"oauth-test-{uuid.uuid4().hex}"
    await redis.set(f"oauth_code:{code}", user_id, ex=60)

    exchange = await client.post("/api/v1/auth/oauth/exchange", json={"code": code})
    assert exchange.status_code == 200
    headers = {"Authorization": f"Bearer {exchange.json()['access_token']}"}

    listed = await client.get("/api/v1/auth/me/oauth", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    unlink = await client.delete("/api/v1/auth/me/oauth/github", headers=headers)
    assert unlink.status_code == 409


async def test_unlink_with_password_ok(client: AsyncClient, test_engine) -> None:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    email = f"oauthpw-{uuid.uuid4().hex[:8]}@moziketo.ir"
    password = "securepass1"
    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "display_name": "OAuth PW"},
    )
    user_id = reg.json()["user"]["id"]

    session_factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        from uuid import UUID

        from app.models import User

        user = await session.get(User, UUID(user_id))
        assert user is not None
        session.add(
            OAuthAccount(
                user_id=user.id,
                provider=OAuthProvider.GOOGLE,
                provider_user_id=f"google-{uuid.uuid4().hex[:8]}",
                email_at_link=email,
            )
        )
        await session.commit()

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    unlink = await client.delete("/api/v1/auth/me/oauth/google", headers=headers)
    assert unlink.status_code == 204

    listed = await client.get("/api/v1/auth/me/oauth", headers=headers)
    assert listed.json() == []
