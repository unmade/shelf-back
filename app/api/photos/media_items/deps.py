from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Query

from app.api.deps import UseCasesDeps
from app.api.photos import exceptions
from app.app.photos.services.media_item import (
    DownloadMediaItem,
    DownloadMediaItemSession,
)

__all__ = [
    "DownloadMediaItemBatchCache",
    "DownloadMediaItemCache",
    "download_media_item_batch_cache",
    "download_media_item_cache",
]


async def _download_session(
    usecases: UseCasesDeps,
    key: str = Query(None),
) -> DownloadMediaItemSession:
    session = await usecases.media_item.get_download_session(key)
    if session is None:
        raise exceptions.DownloadNotFound() from None
    return session


async def download_media_item_cache(
    session: _DownloadMediaItemSessionCache
) -> DownloadMediaItem:
    if len(session) != 1:
        raise exceptions.DownloadNotFound() from None
    return session[0]


async def download_media_item_batch_cache(
    session: _DownloadMediaItemSessionCache
) -> DownloadMediaItemSession:
    if len(session) < 2:
        raise exceptions.DownloadNotFound() from None
    return session


_DownloadMediaItemSessionCache = Annotated[
    DownloadMediaItemSession,
    Depends(_download_session),
]

DownloadMediaItemCache = Annotated[
    DownloadMediaItem,
    Depends(download_media_item_cache),
]
DownloadMediaItemBatchCache = Annotated[
    DownloadMediaItemSession,
    Depends(download_media_item_batch_cache),
]
