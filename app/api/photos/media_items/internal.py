from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import ServiceTokenDeps, UseCasesDeps
from app.api.photos.exceptions import MediaItemNotFound
from app.app.photos.domain import MediaItem

from .schemas import AddCategoryRequest

router = APIRouter()


@router.post("/add_category_batch")
async def auto_add_category_batch(
    _: ServiceTokenDeps,
    payload: AddCategoryRequest,
    usecases: UseCasesDeps,
) -> None:
    """Add categories auto-extracted from image content."""
    file_id = payload.file_id
    categories=[
        (category.name, category.probability)
        for category in payload.categories
    ]
    try:
        await usecases.media_item.auto_add_category_batch(
            file_id, categories=categories
        )
    except MediaItem.NotFound as exc:
        raise MediaItemNotFound() from exc
