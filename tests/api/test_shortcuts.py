from __future__ import annotations

import pytest

from app.api import shortcuts
from app.cache import cache

pytestmark = [pytest.mark.asyncio, pytest.mark.database]


class TestCreateDownloadCache:
    async def test(self):
        key = await shortcuts.create_download_cache("ns_path", "f.txt")
        assert len(key) > 32
        value = await cache.get(key)
        assert value == "ns_path:f.txt"


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
