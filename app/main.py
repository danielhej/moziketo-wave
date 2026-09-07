from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.api.v1.router import router as v1_router
from app.core.config import get_settings
from app.core.logging import setup_logging

OPENAPI_TAGS = [
    {
        "name": "system",
        "description": "Health checks and service metadata.",
    },
    {
        "name": "catalog",
        "description": "Artists, tracks, and catalog search for موزیکتو.",
    },
]


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    setup_logging(settings.debug)
    yield


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
        version="0.1.0",
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

    return app


app = create_app()
