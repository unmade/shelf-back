from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, Request

from app.api.deps import CurrentUserDeps, UseCasesDeps
from app.api.paginator import Page, get_offset

from .schemas import MediaItemSchema

router = APIRouter()


@router.get("/list_media_items")
async def list_media_items(
    request: Request,
    current_user: CurrentUserDeps,
    usecases: UseCasesDeps,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=25, le=100)] = 1000,
) -> Page[MediaItemSchema]:
    """List media items current user has."""
    offset = get_offset(page, page_size)
    items = await usecases.photos.list_media_items(
        current_user.id,
        offset=offset,
        limit=page_size,
    )
    return Page(
        page=page,
        items=[MediaItemSchema.from_entity(item, request) for item in items],
    )
