from __future__ import annotations

import asyncio
from typing import Any


async def gather(*coros) -> list[Any]:
    """Run coros sequence within TaskGroup."""
    async with asyncio.TaskGroup() as tg:
        tasks = tuple(tg.create_task(task) for task in coros)
    return [task.result() for task in tasks]
