from __future__ import annotations

import secrets
from typing import TYPE_CHECKING, NamedTuple
from uuid import UUID

from app import actions, errors
from app.cache import cache, disk_cache
from app.entities import Namespace

from .files import exceptions

if TYPE_CHECKING:
    from app.entities import File
    from app.typedefs import DBClient, StrOrPath


class DownloadCache(NamedTuple):
    ns_path: str
    path: str


async def create_download_cache(ns_path: StrOrPath, path: StrOrPath) -> str:
    """
    Set metadata to be used for file download.

    Args:
        ns_path (StrOrPath): Target namespace.
        path (StrOrPath): File path.

    Returns:
        str: A temporary key to obtain data from the cache.
    """
    token = secrets.token_urlsafe()
    await cache.set(key=token, value=f"{ns_path}:{path}", expire=60)
    return token


def _make_thumbnail_ttl(*args, size, **kwargs) -> str:
    if size < 128:
        return "7d"
    return "24h"


@disk_cache(key="{file_id}:{size}:{mtime}", ttl=_make_thumbnail_ttl)
async def get_cached_thumbnail(
    db_client: DBClient,
    namespace: Namespace,
    file_id: UUID,
    *,
    size: int,
    mtime: float,
) -> tuple[File, bytes]:
    """
    Return a file and thumbnail of a given file ID from cache.

    If thumbnail doesn't exist it will be created and cached first.
    """
    try:
        return await actions.get_thumbnail(
            db_client, namespace, file_id, size=size,
        )
    except errors.FileNotFound as exc:
        raise exceptions.PathNotFound(path=str(file_id)) from exc
    except errors.IsADirectory as exc:
        raise exceptions.IsADirectory(path=str(file_id)) from exc
    except errors.ThumbnailUnavailable as exc:
        raise exceptions.ThumbnailUnavailable(path=str(file_id)) from exc


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
