from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse

from app.api.deps import CurrentUserDeps, UseCasesDeps
from app.api.paginator import Page, get_offset
from app.api.photos import exceptions
from app.api.photos.media_items.deps import DownloadMediaItemBatchCache
from app.app.photos.domain import MediaItem

from .schemas import (
    CountMediaItemsResponse,
    DeleteMediaItemBatchRequest,
    DeleteMediaItemImmediatelyBatchRequest,
    FileIDRequest,
    GetDownloadUrlRequest,
    GetDownloadUrlResponse,
    ListMediaItemCategoriesResponse,
    MediaItemCategorySchema,
    MediaItemSchema,
    MediaItemSharedLinkSchema,
    RestoreMediaItemBatchRequest,
    SetMediaItemCategoriesRequest,
)

router = APIRouter()


@router.get("/count")
async def count_media_items(
    usecases: UseCasesDeps,
    user: CurrentUserDeps,
) -> CountMediaItemsResponse:
    """Returns total number of media items."""
    result = await usecases.media_item.count(user.id)
    return CountMediaItemsResponse(total=result.total, deleted=result.deleted)


@router.post("/delete_batch")
async def delete_media_item_batch(
    request: Request,
    payload: DeleteMediaItemBatchRequest,
    usecases: UseCasesDeps,
    user: CurrentUserDeps,
) -> Page[MediaItemSchema]:
    """Delete multiple media items at once."""
    items = await usecases.media_item.delete_batch(user.id, payload.file_ids)
    return Page(
        page=1,
        items=[MediaItemSchema.from_entity(item, request) for item in items]
    )


@router.post("/delete_immediately_batch")
async def delete_media_item_immediately_batch(
    payload: DeleteMediaItemImmediatelyBatchRequest,
    usecases: UseCasesDeps,
    user: CurrentUserDeps,
) -> None:
    """Delete multiple media items at once."""
    await usecases.media_item.delete_immediately_batch(user.id, payload.file_ids)


@router.get("/download_batch")
def download_media_items_batch(
    usecases: UseCasesDeps,
    value: DownloadMediaItemBatchCache,
):
    """
    Downloads multiple media items as a zip archive.
    """
    content = usecases.media_item.download_batch(value)
    filename = "Shelf Cloud.zip"
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Content-Type": "attachment/zip",
    }
    return StreamingResponse(content, headers=headers)


@router.post("/get_download_url")
async def get_download_url(
    request: Request,
    payload: GetDownloadUrlRequest,
    usecases: UseCasesDeps,
    user: CurrentUserDeps,
) -> GetDownloadUrlResponse:
    """Return a link to download requested media items."""
    key = await usecases.media_item.download_batch_create_session(
        user.id, payload.file_ids
    )
    download_url = request.url_for("download_media_items_batch")
    return GetDownloadUrlResponse(download_url=f"{download_url}?key={key}")


@router.get("/list")
async def list_media_items(
    request: Request,
    user: CurrentUserDeps,
    usecases: UseCasesDeps,
    favourites: Annotated[bool, Query(...)] = False,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=100, le=1000)] = 100,
) -> Page[MediaItemSchema]:
    """Lists media items current user has."""
    offset = get_offset(page, page_size)
    items = await usecases.media_item.list_(
        user.id,
        only_favourites=favourites,
        offset=offset,
        limit=page_size,
    )
    return Page(
        page=page,
        items=[MediaItemSchema.from_entity(item, request) for item in items],
    )


@router.get("/list_deleted")
async def list_deleted_media_items(
    request: Request,
    usecases: UseCasesDeps,
    user: CurrentUserDeps,
) -> Page[MediaItemSchema]:
    """Lists all user's deleted media items."""
    items = await usecases.media_item.list_deleted(user.id)
    return Page(
        page=1,
        items=[MediaItemSchema.from_entity(item, request) for item in items]
    )


@router.post("/list_categories")
async def list_media_item_categories(
    payload: FileIDRequest,
    usecases: UseCasesDeps,
    user: CurrentUserDeps,
) -> ListMediaItemCategoriesResponse:
    """Return all categories for the specified media item."""
    try:
        categories = await usecases.media_item.list_categories(
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


@router.get("/list_shared_links")
async def list_shared_links(
    request: Request,
    user: CurrentUserDeps,
    usecases: UseCasesDeps,
) -> Page[MediaItemSharedLinkSchema]:
    """Lists shared links."""
    items = await usecases.media_item.list_shared_links(user.id)
    return Page(
        page=1,
        items=[
            MediaItemSharedLinkSchema.from_entity(item, link, request=request)
            for item, link in items
        ]
    )


@router.post("/purge")
async def purge(
    usecases: UseCasesDeps,
    user: CurrentUserDeps,
) -> None:
    """Deletes immediately all deleted items"""
    await usecases.media_item.purge(user.id)


@router.post("/restore_batch")
async def restore_media_item_batch(
    request: Request,
    payload: RestoreMediaItemBatchRequest,
    usecases: UseCasesDeps,
    user: CurrentUserDeps,
) -> Page[MediaItemSchema]:
    """Restores multiple deleted media items at once."""
    items = await usecases.media_item.restore_batch(user.id, payload.file_ids)
    return Page(
        page=1,
        items=[MediaItemSchema.from_entity(item, request) for item in items]
    )


@router.post("/set_categories")
async def set_media_item_categories(
    payload: SetMediaItemCategoriesRequest,
    usecases: UseCasesDeps,
    user: CurrentUserDeps,
) -> None:
    """Clears existing and sets specified categories for the media item."""
    try:
        await usecases.media_item.set_categories(
            user.id,
            payload.file_id,
            categories=payload.categories,
        )
    except MediaItem.NotFound as exc:
        raise exceptions.MediaItemNotFound() from exc
