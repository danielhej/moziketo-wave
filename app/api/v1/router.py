from fastapi import APIRouter

from app.api.v1 import (
    admin,
    admin_analytics,
    albums,
    auth,
    browse,
    catalog,
    favorites,
    history,
    playback,
    playlists,
    recommendations,
    taxonomy,
    uploads,
)

router = APIRouter()
router.include_router(catalog.router)
router.include_router(albums.router)
router.include_router(browse.router)
router.include_router(taxonomy.router)
router.include_router(playlists.router)
router.include_router(playlists.me_router)
router.include_router(auth.router)
router.include_router(favorites.router)
router.include_router(history.router)
router.include_router(recommendations.router)
router.include_router(recommendations.catalog_router)
router.include_router(playback.router)
router.include_router(admin.router)
router.include_router(admin_analytics.router)
router.include_router(uploads.router)
router.include_router(uploads.me_router)
