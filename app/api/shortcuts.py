from __future__ import annotations

import secrets
from typing import TYPE_CHECKING, NamedTuple

from app.cache import cache

if TYPE_CHECKING:
    from app.app.files.domain import AnyFile


class DownloadCache(NamedTuple):
    ns_path: str
    path: str


async def create_download_cache(file: AnyFile) -> str:
    """Set metadata to be used for a file download."""
    token = secrets.token_urlsafe()
    await cache.set(key=token, value=file, expire=60)
    return token


async def pop_download_cache(token: str) -> AnyFile | None:
    """Return download metadata and remove it from cache."""
    value: str | None = await cache.get(token)
    if not value:
        return None
    await cache.delete(token)
    return value  # type: ignore[return-value]
