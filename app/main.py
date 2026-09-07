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
    {"name": "catalog", "description": "Artists, tracks, browse, taxonomy, and search."},
    {"name": "auth", "description": "Registration, login, and JWT token management."},
    {"name": "favorites", "description": "User favorite tracks (requires Bearer token)."},
    {"name": "playlists", "description": "Editorial and user playlists."},
    {"name": "playback", "description": "Stream and download redirects to CDN."},
    {"name": "admin", "description": "Admin operations (requires X-Admin-Key header)."},
]


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    setup_logging(settings.debug)
    try:
        await connect_redis()
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
            "- OpenAPI schema: [`/openapi.json`](/openapi.json)\n"
            "- Swagger UI: [`/docs`](/docs) or [`/swagger`](/swagger)\n"
            "- ReDoc: [`/redoc`](/redoc)"
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
            },
            "AdminKey": {
                "type": "apiKey",
                "in": "header",
                "name": "X-Admin-Key",
            },
        }
        app.openapi_schema = schema
        return schema

    app.openapi = custom_openapi  # type: ignore[method-assign]

    return app


app = create_app()
