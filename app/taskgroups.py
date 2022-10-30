from __future__ import annotations

import asyncio
from typing import Any, Awaitable


async def gather(*coros: Awaitable[Any]) -> list[Any]:
    """Run coros sequence within TaskGroup."""
    async with asyncio.TaskGroup() as tg:  # type: ignore[attr-defined]
        tasks = [tg.create_task(task) for task in coros]
    return [task.result() for task in tasks]
