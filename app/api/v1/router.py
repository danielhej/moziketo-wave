from fastapi import APIRouter

from app.api.v1 import admin, auth, catalog, favorites, playback

router = APIRouter()
router.include_router(catalog.router)
router.include_router(auth.router)
router.include_router(favorites.router)
router.include_router(playback.router)
router.include_router(admin.router)
