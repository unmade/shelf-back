from fastapi import APIRouter

from .albums.views import router as albums_router
from .media_items.internal import router as media_items_internal_router
from .media_items.views import router as media_items_router

__all__ = [
    "router",
]


router = APIRouter()

router.include_router(albums_router, prefix="/albums", tags=["albums"])
router.include_router(media_items_router, prefix="/media_items", tags=["media_items"])
router.include_router(
    media_items_internal_router, prefix="/-/media_items", include_in_schema=False
)
