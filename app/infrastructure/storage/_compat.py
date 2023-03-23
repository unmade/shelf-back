from __future__ import annotations

import asyncio

_sentinel = object()


async def iter_async(it):
    loop = asyncio.get_running_loop()
    while True:
        value = await loop.run_in_executor(None, next, it, _sentinel)
        if value is _sentinel:
            break
        yield value
