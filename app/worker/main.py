from __future__ import annotations

from contextlib import AsyncExitStack
from typing import TYPE_CHECKING, TypedDict

from arq.connections import RedisSettings

from app.config import config
from app.infrastructure.context import AppContext
from app.worker.jobs import files

if TYPE_CHECKING:
    from app.infrastructure.context import UseCases

    class ARQContext(TypedDict):
        usecases: UseCases
        _stack: AsyncExitStack


async def startup(ctx: ARQContext):
    app_ctx = AppContext(config.database, config.storage, config.worker)
    ctx["_stack"] = AsyncExitStack()
    await ctx["_stack"].enter_async_context(app_ctx)
    ctx["usecases"] = app_ctx.usecases


async def shutdown(ctx: ARQContext):
    await ctx["_stack"].aclose()


async def ping(ctx):
    return "pong"


class WorkerSettings:
    functions = [
        ping,
        files.delete_immediately_batch,
        files.empty_trash,
        files.move_batch,
        files.move_to_trash_batch,
    ]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(config.worker.broker_dsn)
