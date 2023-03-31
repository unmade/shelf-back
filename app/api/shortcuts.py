from __future__ import annotations

import secrets
from typing import TYPE_CHECKING, NamedTuple

from app.cache import cache

if TYPE_CHECKING:
    from app.app.files.domain import AnyPath


class DownloadCache(NamedTuple):
    ns_path: str
    path: str


async def create_download_cache(ns_path: AnyPath, path: AnyPath) -> str:
    """
    Set metadata to be used for file download.

    Args:
        ns_path (AnyPath): Target namespace.
        path (AnyPath): File path.

    Returns:
        str: A temporary key to obtain data from the cache.
    """
    token = secrets.token_urlsafe()
    await cache.set(key=token, value=f"{ns_path}:{path}", expire=60)
    return token


async def pop_download_cache(token: str) -> DownloadCache | None:
    """
    Return download metadata and remove it from cache.

    Args:
        token (str): A key returned by `create_download_cache` method.

    Returns:
        DownloadCache | None: Namespace path and file path respectively or None if
            download metadata does not exist or expired.
    """
    value: str = await cache.get(token)
    if not value:
        return None
    await cache.delete(token)
    return DownloadCache(*value.split(":", maxsplit=1))
