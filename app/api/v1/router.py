from fastapi import APIRouter

from app.api.v1 import catalog

router = APIRouter()
router.include_router(catalog.router)
