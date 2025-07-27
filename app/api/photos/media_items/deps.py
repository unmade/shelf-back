from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Query

from app.api.deps import UseCasesDeps
from app.api.photos.exceptions import DownloadNotFound
from app.app.photos.usecases.media_item import DownloadBatchSession


async def download_media_item_batch_cache(
    usecases: UseCasesDeps,
    key: str = Query(None),
) -> DownloadBatchSession:
    value = await usecases.media_item.download_batch_get_session(key)
    if value is None:
        raise DownloadNotFound()
    return value


DownloadMediaItemBatchCache = Annotated[
    DownloadBatchSession,
    Depends(download_media_item_batch_cache),
]
