import os

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

os.environ["DISABLE_CACHE"] = "1"
os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("DEBUG", "true")
os.environ.setdefault("AUTH_RATE_LIMIT_ENABLED", "false")

from app.api.deps import get_db_session
from app.core.config import get_settings
from app.core.redis import connect_redis, disconnect_redis
from app.main import app

settings = get_settings()


@pytest.fixture(autouse=True)
def _disable_auth_rate_limit_by_default(
    monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> None:
    if "low_rate_limits" in request.fixturenames:
        return
    monkeypatch.setattr(settings, "auth_rate_limit_enabled", False)
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "debug", True)


@pytest.fixture(autouse=True)
async def redis_connection():
    from app.core import redis as redis_module

    redis_module._redis = None
    try:
        await connect_redis()
    except Exception:
        pass
    yield
    await disconnect_redis()


@pytest.fixture
async def test_engine():
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    yield engine
    await engine.dispose()


@pytest.fixture
async def client(test_engine):
    session_factory = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
async def auth_headers(client: AsyncClient) -> dict[str, str]:
    import uuid

    email = f"test-{uuid.uuid4().hex[:8]}@moziketo.ir"
    password = "testpass123"
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "display_name": "Test User"},
    )
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
