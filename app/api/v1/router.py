from fastapi import APIRouter

from app.api.v1 import admin, auth, browse, catalog, favorites, playback, playlists, taxonomy

router = APIRouter()
router.include_router(catalog.router)
router.include_router(browse.router)
router.include_router(taxonomy.router)
router.include_router(playlists.router)
router.include_router(playlists.me_router)
router.include_router(auth.router)
router.include_router(favorites.router)
router.include_router(playback.router)
router.include_router(admin.router)
