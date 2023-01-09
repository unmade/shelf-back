from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

import pytest

from app.api import shortcuts
from app.api.files.exceptions import (
    IsADirectory,
    PathNotFound,
    ThumbnailUnavailable,
)
from app.api.files.schemas import ThumbnailSize
from app.cache import cache, disk_cache

if TYPE_CHECKING:
    from io import BytesIO

    from app.entities import Namespace
    from app.typedefs import DBTransaction
    from tests.factories import FileFactory, FolderFactory

pytestmark = [pytest.mark.asyncio, pytest.mark.database]


class TestCreateDownloadCache:
    async def test(self):
        key = await shortcuts.create_download_cache("ns_path", "f.txt")
        assert len(key) > 32
        value = await cache.get(key)
        assert value == "ns_path:f.txt"


class TestMakeThumbnailTTL:
    def test_small_size(self):
        assert shortcuts._make_thumbnail_ttl(size=64) == "7d"

    def test_large_size(self):
        assert shortcuts._make_thumbnail_ttl(size=256) == "24h"


class TestGetCachedThumbnail:
    async def test_get_thumbnail_sets_disk_cache_on_cache_miss(
        self,
        tx: DBTransaction,
        namespace: Namespace,
        file_factory: FileFactory,
        image_content: BytesIO,
    ):
        file = await file_factory(namespace.path, content=image_content)
        mtime = file.mtime
        size = ThumbnailSize.xs.asint()
        key = f"{file.id}:{size}:{mtime}"
        value = await disk_cache.get(key, default=None)
        assert value is None
        await shortcuts.get_cached_thumbnail(
            tx, namespace, file.id, size=size, mtime=mtime
        )
        file, thumb = await disk_cache.get(key, default=None)
        assert thumb is not None

    async def test_get_thumbnail_hits_disk_cache(
        self,
        tx: DBTransaction,
        namespace: Namespace,
        image_content: BytesIO,
    ):
        file_id = str(uuid.uuid4())
        mtime = datetime.now().timestamp()
        size = ThumbnailSize.xs.asint()
        content = image_content.read()

        key = f"{file_id}:{size}:{mtime}"
        value = file_id, content
        await disk_cache.set(key, value=value, expire=60)

        result = await shortcuts.get_cached_thumbnail(
            tx, namespace, file_id, size=size, mtime=mtime
        )
        assert result == value

    async def test_get_thumbnail_but_path_not_found(
        self,
        tx: DBTransaction,
        namespace: Namespace,
    ):
        file_id = str(uuid.uuid4())
        mtime = datetime.now().timestamp()
        size = ThumbnailSize.sm.asint()
        with pytest.raises(PathNotFound) as excinfo:
            await shortcuts.get_cached_thumbnail(
                tx, namespace, file_id, size=size, mtime=mtime
            )
        assert str(excinfo.value) == str(PathNotFound(path=file_id))

    async def test_get_thumbnail_but_path_is_a_folder(
        self,
        tx: DBTransaction,
        namespace: Namespace,
        folder_factory: FolderFactory,
    ):
        folder = await folder_factory(namespace.path)
        mtime = folder.mtime
        size = ThumbnailSize.xs.asint()
        with pytest.raises(IsADirectory) as excinfo:
            await shortcuts.get_cached_thumbnail(
                tx, namespace, folder.id, size=size, mtime=mtime
            )
        assert str(excinfo.value) == str(IsADirectory(path=folder.id))

    async def test_get_thumbnail_but_file_is_not_thumbnailable(
        self,
        tx: DBTransaction,
        namespace: Namespace,
        file_factory: FileFactory,
    ):
        file = await file_factory(namespace.path)
        mtime = file.mtime
        size = ThumbnailSize.xs.asint()
        with pytest.raises(ThumbnailUnavailable) as excinfo:
            await shortcuts.get_cached_thumbnail(
                tx, namespace, file.id, size=size, mtime=mtime
            )
        assert str(excinfo.value) == str(ThumbnailUnavailable(path=file.id))


class TestPopDownloadCache:
    async def test(self):
        key = "secret-key"
        await cache.set(key, "ns_path:f.txt")
        value = await shortcuts.pop_download_cache(key)
        assert value is not None
        assert value.ns_path == "ns_path"
        assert value.path == "f.txt"
        assert await cache.get(key) is None

    async def test_split_correctly(self):
        key = "secret-key"
        await cache.set(key, "ns_path:a/b/f:1.txt")
        value = await shortcuts.pop_download_cache(key)
        assert value is not None
        assert value.ns_path == "ns_path"
        assert value.path == "a/b/f:1.txt"

    async def test_cache_miss(self):
        value = await shortcuts.pop_download_cache("key-not-exists")
        assert value is None
