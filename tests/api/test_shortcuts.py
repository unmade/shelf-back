from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest

from app.api import shortcuts
from app.app.files.domain import File, Path
from app.cache import cache

if TYPE_CHECKING:
    from app.app.files.domain import AnyPath

pytestmark = [pytest.mark.anyio, pytest.mark.database]


def _make_file(
    ns_path: AnyPath, path: AnyPath, size: int = 10, mediatype: str = "plain/text"
) -> File:
    return File(
        id=uuid.uuid4(),
        ns_path=str(ns_path),
        name=Path(path).name,
        path=Path(path),
        size=size,
        mediatype=mediatype,
    )


class TestCreateDownloadCache:
    async def test(self):
        # GIVEN
        file = _make_file("admin", "f.txt")
        # WHEN
        key = await shortcuts.create_download_cache(file)
        # THEN
        assert len(key) > 32
        value = await cache.get(key)
        assert value == file


class TestPopDownloadCache:
    async def test(self):
        # GIVEN
        key, file = "secret-key", _make_file("admin", "f.txt")
        await cache.set(key, file)
        # WHEN
        value = await shortcuts.pop_download_cache(key)
        # THEN
        assert value == file
        assert await cache.get(key) is None

    async def test_cache_miss(self):
        value = await shortcuts.pop_download_cache("key-not-exists")
        assert value is None
