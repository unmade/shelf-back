from __future__ import annotations

import asyncio

import pytest

from app.toolkit import taskgroups

pytestmark = [pytest.mark.anyio]


async def coro(value: int) -> int:
    await asyncio.sleep(0.05)
    return value


async def test_gather():
    results = await taskgroups.gather(coro(0), coro(1), coro(2))
    assert results == [0, 1, 2]
