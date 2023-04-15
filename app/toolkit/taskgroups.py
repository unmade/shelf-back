from __future__ import annotations

import asyncio
import contextlib
from typing import Any

_background_tasks = set()


async def gather(*coros) -> list[Any]:
    """Run coros sequence within TaskGroup."""
    async with asyncio.TaskGroup() as tg:
        tasks = tuple(tg.create_task(task) for task in coros)
    return [task.result() for task in tasks]


def schedule(coro) -> None:
    """Runs coroutine in the background."""
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


async def wait_background_tasks(timeout: int | float | None = None) -> None:
    """Waits for background tasks to complete"""
    with contextlib.suppress(ValueError):
        await asyncio.wait(_background_tasks, timeout=timeout)
