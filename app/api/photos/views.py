from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, Request

from app.api.deps import CurrentUserDeps, UseCasesDeps
from app.api.paginator import Page, get_offset
from app.api.photos import exceptions
from app.app.photos.domain import MediaItem

from .schemas import (
    CountMediaItemsResponse,
    DeleteMediaItemBatchRequest,
    DeleteMediaItemImmediatelyBatchRequest,
    FileIDRequest,
    ListMediaItemCategoriesResponse,
    MediaItemCategorySchema,
    MediaItemSchema,
    MediaItemSharedLinkSchema,
    RestoreMediaItemBatchRequest,
    SetMediaItemCategoriesRequest,
)

router = APIRouter()


@router.get("/count_media_items")
async def count_media_items(
    usecases: UseCasesDeps,
    user: CurrentUserDeps,
) -> CountMediaItemsResponse:
    """Returns total number of media items."""
    result = await usecases.photos.count_media_items(user.id)
    return CountMediaItemsResponse(total=result.total, deleted=result.deleted)


@router.post("/delete_media_item_batch")
async def delete_media_item_batch(
    request: Request,
    payload: DeleteMediaItemBatchRequest,
    usecases: UseCasesDeps,
    user: CurrentUserDeps,
) -> Page[MediaItemSchema]:
    """Delete multiple media items at once."""
    items = await usecases.photos.delete_media_item_batch(user.id, payload.file_ids)
    return Page(
        page=1,
        items=[MediaItemSchema.from_entity(item, request) for item in items]
    )


@router.post("/delete_media_item_immediately_batch")
async def delete_media_item_immediately_batch(
    payload: DeleteMediaItemImmediatelyBatchRequest,
    usecases: UseCasesDeps,
    user: CurrentUserDeps,
) -> None:
    """Delete multiple media items at once."""
    await usecases.photos.delete_media_item_immediately_batch(user.id, payload.file_ids)


@router.post("/empty_trash")
async def empty_trash(
    usecases: UseCasesDeps,
    user: CurrentUserDeps,
) -> None:
    await usecases.photos.empty_trash(user.id)


@router.get("/list_deleted_media_items")
async def list_deleted_media_items(
    request: Request,
    usecases: UseCasesDeps,
    user: CurrentUserDeps,
) -> Page[MediaItemSchema]:
    """Lists all user's deleted media items."""
    items = await usecases.photos.list_deleted_media_items(user.id)
    return Page(
        page=1,
        items=[MediaItemSchema.from_entity(item, request) for item in items]
    )


@router.get("/list_media_items")
async def list_media_items(
    request: Request,
    user: CurrentUserDeps,
    usecases: UseCasesDeps,
    favourites: Annotated[bool, Query(...)] = False,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=100, le=1000)] = 100,
) -> Page[MediaItemSchema]:
    """List media items current user has."""
    offset = get_offset(page, page_size)
    items = await usecases.photos.list_media_items(
        user.id,
        only_favourites=favourites,
        offset=offset,
        limit=page_size,
    )
    return Page(
        page=page,
        items=[MediaItemSchema.from_entity(item, request) for item in items],
    )


@router.get("/list_shared_links")
async def list_shared_links(
    request: Request,
    user: CurrentUserDeps,
    usecases: UseCasesDeps,
) -> Page[MediaItemSharedLinkSchema]:
    """Lists shared links."""
    items = await usecases.photos.list_shared_links(user.id)
    return Page(
        page=1,
        items=[
            MediaItemSharedLinkSchema.from_entity(item, link, request=request)
            for item, link in items
        ]
    )


@router.post("/list_media_item_categories")
async def list_media_item_categories(
    payload: FileIDRequest,
    usecases: UseCasesDeps,
    user: CurrentUserDeps,
) -> ListMediaItemCategoriesResponse:
    try:
        categories = await usecases.photos.list_media_item_categories(
            user.id, payload.file_id
        )
    except MediaItem.NotFound as exc:
        raise exceptions.MediaItemNotFound() from exc

    return ListMediaItemCategoriesResponse(
        file_id=payload.file_id,
        categories=[
            MediaItemCategorySchema.from_entity(category)
            for category in categories
        ]
    )


@router.post("/restore_media_item_batch")
async def restore_media_item_batch(
    request: Request,
    payload: RestoreMediaItemBatchRequest,
    usecases: UseCasesDeps,
    user: CurrentUserDeps,
) -> Page[MediaItemSchema]:
    """Restores multiple deleted media items at once."""
    items = await usecases.photos.restore_media_item_batch(user.id, payload.file_ids)
    return Page(
        page=1,
        items=[MediaItemSchema.from_entity(item, request) for item in items]
    )


@router.post("/set_media_item_categories")
async def set_media_item_categories(
    payload: SetMediaItemCategoriesRequest,
    usecases: UseCasesDeps,
    user: CurrentUserDeps,
) -> None:
    try:
        await usecases.photos.set_media_item_categories(
            user.id,
            payload.file_id,
            categories=payload.categories,
        )
    except MediaItem.NotFound as exc:
        raise exceptions.MediaItemNotFound() from exc
