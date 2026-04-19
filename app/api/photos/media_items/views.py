from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, Query, Request
from fastapi.responses import Response, StreamingResponse

from app.api.deps import CurrentUserDeps, UseCasesDeps
from app.api.files.schemas import ThumbnailSize
from app.api.paginator import Page, get_offset
from app.api.photos import exceptions
from app.app.blobs.domain import Blob, BlobMetadata
from app.app.photos.domain import MediaItem
from app.cache import disk_cache

from .deps import DownloadMediaItemBatchCache, DownloadMediaItemCache
from .schemas import (
    AddFavouriteBatchRequest,
    CountMediaItemsResponse,
    DeleteMediaItemBatchRequest,
    DeleteMediaItemImmediatelyBatchRequest,
    GetContentMetadataResponse,
    GetDownloadUrlRequest,
    GetDownloadUrlResponse,
    ListFavouriteMediaItemsResponse,
    ListMediaItemCategoriesResponse,
    MediaItemCategorySchema,
    MediaItemIDRequest,
    MediaItemSchema,
    RemoveFavouriteBatchRequest,
    RestoreMediaItemBatchRequest,
    SetMediaItemCategoriesRequest,
    UploadContent,
)

router = APIRouter()


def _make_thumbnail_ttl(*args, size: ThumbnailSize, **kwargs) -> str:
    size = ThumbnailSize(size)
    if size.asint() == ThumbnailSize.xs.asint():
        return "7d"
    return "24h"


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
    items = await usecases.media_item.delete_batch(user.id, payload.ids)
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
    """Delete multiple media items permanently."""
    await usecases.media_item.delete_immediately_batch(user.id, payload.ids)


@router.get("/download", name="download_media_item")
def download_media_item(
    usecases: UseCasesDeps,
    item: DownloadMediaItemCache,
):
    """Download a single media item from a one-time session."""
    content = usecases.media_item.download(item)
    filename = item.name.encode("utf-8").decode("latin-1")
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Content-Length": str(item.size),
        "Content-Type": item.media_type,
    }
    return StreamingResponse(content, headers=headers)


@router.get("/download_batch", name="download_media_items_batch")
def download_media_items_batch(
    usecases: UseCasesDeps,
    items: DownloadMediaItemBatchCache,
):
    """Download multiple media items as a ZIP archive."""
    content = usecases.media_item.download_batch(items)
    filename = "Shelf Cloud.zip"
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Content-Type": "attachment/zip",
    }
    return StreamingResponse(content, headers=headers)


@router.post("/get_content_metadata")
async def get_content_metadata(
    payload: MediaItemIDRequest,
    usecases: UseCasesDeps,
    user: CurrentUserDeps,
) -> GetContentMetadataResponse:
    """Return content metadata for the specified media item."""
    try:
        metadata = await usecases.media_item.get_content_metadata(
            user.id, payload.media_item_id
        )
    except MediaItem.NotFound as exc:
        raise exceptions.MediaItemNotFound() from exc
    except BlobMetadata.NotFound as exc:
        raise exceptions.MediaItemContentMetadataNotFound(
            media_item_id=payload.media_item_id
        ) from exc

    return GetContentMetadataResponse.from_entity(
        payload.media_item_id,
        metadata,
    )


@router.post("/get_download_url")
async def get_download_url(
    request: Request,
    payload: GetDownloadUrlRequest,
    usecases: UseCasesDeps,
    user: CurrentUserDeps,
) -> GetDownloadUrlResponse:
    """Return a one-time download link for one or many media items."""
    try:
        session = await usecases.media_item.create_download_session(
            user.id, payload.ids
        )
    except MediaItem.NotFound as exc:
        raise exceptions.MediaItemNotFound() from exc

    if session.items_count == 1:
        download_url = request.url_for("download_media_item")
    else:
        download_url = request.url_for("download_media_items_batch")
    return GetDownloadUrlResponse(download_url=f"{download_url}?key={session.key}")


@router.post("/favourites/mark_batch")
async def mark_favourite_batch(
    payload: AddFavouriteBatchRequest,
    usecases: UseCasesDeps,
    user: CurrentUserDeps,
) -> None:
    """Marks multiple media items as favourite."""
    await usecases.media_item.mark_favourite_batch(user.id, payload.ids)


@router.get("/favourites/list")
async def list_favourite_media_item_ids(
    usecases: UseCasesDeps,
    user: CurrentUserDeps,
) -> ListFavouriteMediaItemsResponse:
    """Lists favourited media item IDs for the current user."""
    ids = await usecases.media_item.list_favourite_ids(user.id)
    return ListFavouriteMediaItemsResponse(ids=ids)


@router.post("/favourites/unmark_batch")
async def unmark_favourite_batch(
    payload: RemoveFavouriteBatchRequest,
    usecases: UseCasesDeps,
    user: CurrentUserDeps,
) -> None:
    """Removes favourite marks from multiple media items."""
    await usecases.media_item.unmark_favourite_batch(user.id, payload.ids)


@router.get(
    "/get_thumbnail/{media_item_id}",
    name="get_media_item_thumbnail",
)
@disk_cache(
    key="{media_item_id}:{size}",
    ttl=_make_thumbnail_ttl,
    tags=["thumbnails:{media_item_id}"],
)
async def get_thumbnail(
    media_item_id: str,
    size: str,
    usecases: UseCasesDeps,
    user: CurrentUserDeps,
):
    """Get thumbnail for an image media item."""
    item_id = UUID(media_item_id)
    thumbnail_size = ThumbnailSize(size)

    try:
        item, thumbnail, mediatype = await usecases.media_item.thumbnail(
            user.id, item_id, thumbnail_size.asint()
        )
    except Blob.ThumbnailUnavailable as exc:
        raise exceptions.ThumbnailUnavailable() from exc
    except MediaItem.NotFound as exc:
        raise exceptions.MediaItemNotFound() from exc

    filename = item.name.encode("utf-8").decode("latin-1")
    headers = {
        "Content-Disposition": f'inline; filename="{filename}"',
        "Content-Length": str(len(thumbnail)),
        "Content-Type": mediatype.value,
        "Cache-Control": "private, max-age=31536000, no-transform",
    }

    return Response(thumbnail, headers=headers)


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
    payload: MediaItemIDRequest,
    usecases: UseCasesDeps,
    user: CurrentUserDeps,
) -> ListMediaItemCategoriesResponse:
    """Return all categories for the specified media item."""
    try:
        categories = await usecases.media_item.list_categories(
            user.id, payload.media_item_id
        )
    except MediaItem.NotFound as exc:
        raise exceptions.MediaItemNotFound() from exc

    return ListMediaItemCategoriesResponse(
        media_item_id=payload.media_item_id,
        categories=[
            MediaItemCategorySchema.from_entity(category)
            for category in categories
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
    items = await usecases.media_item.restore_batch(user.id, payload.ids)
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
            payload.media_item_id,
            categories=payload.categories,
        )
    except MediaItem.NotFound as exc:
        raise exceptions.MediaItemNotFound() from exc


@router.post("/upload")
async def upload_media_item(
    request: Request,
    user: CurrentUserDeps,
    usecases: UseCasesDeps,
    file: Annotated[UploadContent, File(...)],
) -> MediaItemSchema:
    """Upload a new media item."""
    item = await usecases.media_item.upload(
        owner_id=user.id,
        name=file.filename or "untitled",
        content=file,
        media_type=file.content_type or "application/octet-stream",
    )
    return MediaItemSchema.from_entity(item, request)
