from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import RedirectResponse

from app.api.v1.router import router as v1_router
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.core.redis import connect_redis, disconnect_redis

OPENAPI_TAGS = [
    {"name": "system", "description": "Health checks and service metadata."},
    {"name": "catalog", "description": "Artists, tracks, albums, browse, taxonomy, and search."},
    {
        "name": "history",
        "description": "Listening history and play events (**BearerAuth** required).",
    },
    {
        "name": "recommendations",
        "description": "Personalized recommendations and similar tracks.",
    },
    {
        "name": "uploads",
        "description": "Avatar and admin media uploads to object storage.",
    },
    {
        "name": "auth",
        "description": (
            "Authentication: register, login, JWT refresh, password reset, and OAuth "
            "(Google, GitHub). Apple Sign In is disabled until configured. "
            "Protected routes use **BearerAuth**."
        ),
    },
    {
        "name": "favorites",
        "description": "User favorite tracks (**BearerAuth** required).",
    },
    {
        "name": "playlists",
        "description": "Editorial playlists (public) and user playlists (**BearerAuth**).",
    },
    {"name": "playback", "description": "Stream and download redirects to CDN."},
    {"name": "admin", "description": "Admin operations (**X-Admin-Key** header)."},
]


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    setup_logging(settings.debug)
    try:
        await connect_redis()
    except Exception:
        pass
    try:
        from app.services.search_meili import ensure_indexes

        await ensure_indexes()
    except Exception:
        pass
    yield
    await disconnect_redis()


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Moziketo Wave",
        description=(
            "FastAPI backend for **موزیکتو** — Persian music streaming & download.\n\n"
            "## Docs\n"
            "- OpenAPI schema: [`/openapi.json`](/openapi.json)\n"
            "- Swagger UI: [`/docs`](/docs)\n"
            "- ReDoc: [`/redoc`](/redoc)\n\n"
            "## Auth flows\n\n"
            "### Email/password\n"
            "1. `POST /auth/register` → create account (+ optional verify token in dev)\n"
            "2. `POST /auth/login` → `{ access_token, refresh_token }`\n"
            "3. `PATCH /auth/me`, `POST /auth/change-password`, `POST /auth/set-password`\n"
            "4. `GET /auth/verify-email/confirm?token=` — soft verification (login not blocked)\n"
            "5. Use `Authorization: Bearer <access_token>` on protected routes\n"
            "6. `POST /auth/refresh` to rotate tokens\n\n"
            "### Password reset\n"
            "1. `POST /auth/forgot-password` — sends email when SMTP configured, else dev token\n"
            "2. `POST /auth/reset-password` with token + new password\n\n"
            "### OAuth (Google / GitHub)\n"
            "1. Browser: `GET /auth/oauth/{provider}`\n"
            "2. Frontend receives redirect with `?code=` at `/auth/callback`\n"
            "3. `POST /auth/oauth/exchange` → JWT tokens\n"
            "4. `GET /auth/me/oauth`, `DELETE /auth/me/oauth/{provider}` to manage links\n\n"
            "### Admin\n"
            "Catalog import and ops under `/admin/*` with **X-Admin-Key**.\n\n"
            "Rate limits apply on login, register, and forgot-password (429 + Retry-After)."
        ),
        version="0.2.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        openapi_tags=OPENAPI_TAGS,
        servers=[
            {"url": "https://api.moziketo.ir", "description": "Production"},
            {"url": "http://localhost:8000", "description": "Local development"},
        ],
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(v1_router, prefix=settings.api_v1_prefix)

    @app.get("/", tags=["system"], summary="Service index")
    async def root() -> dict[str, str]:
        return {
            "service": settings.app_name,
            "openapi": "/openapi.json",
            "swagger": "/docs",
            "redoc": "/redoc",
            "health": f"{settings.api_v1_prefix}/health",
        }

    @app.get("/swagger", include_in_schema=False)
    async def swagger_redirect() -> RedirectResponse:
        return RedirectResponse(url="/docs")

    def custom_openapi() -> dict:
        if app.openapi_schema:
            return app.openapi_schema
        schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
            tags=OPENAPI_TAGS,
            servers=app.servers,
        )
        schema["components"]["securitySchemes"] = {
            "BearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
                "description": "Access token from POST /auth/login or /auth/oauth/exchange",
            },
            "AdminKey": {
                "type": "apiKey",
                "in": "header",
                "name": "X-Admin-Key",
                "description": "Admin API key for import endpoints",
            },
        }
        for path, methods in schema.get("paths", {}).items():
            needs_bearer = (
                path.endswith("/auth/me")
                or "/me/favorites" in path
                or "/me/playlists" in path
                or "/me/plays" in path
                or "/me/history" in path
                or "/me/recommendations" in path
                or "/me/uploads" in path
            )
            if needs_bearer:
                for method in methods.values():
                    if isinstance(method, dict):
                        method.setdefault("security", [{"BearerAuth": []}])
            if "/admin/" in path:
                for method in methods.values():
                    if isinstance(method, dict):
                        method.setdefault("security", [{"AdminKey": []}])
        app.openapi_schema = schema
        return schema

    app.openapi = custom_openapi  # type: ignore[method-assign]

    return app


app = create_app()
