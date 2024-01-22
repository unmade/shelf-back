from __future__ import annotations

import contextlib
from contextlib import AbstractAsyncContextManager
from typing import AsyncIterator, TypedDict

import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.app.infrastructure.worker import IWorker
from app.config import config
from app.infrastructure.context import AppContext, UseCases

from . import exceptions, router

sentry_sdk.init(
    config.sentry.dsn,
    environment=config.sentry.environment,
    release=f"shelf@{config.app_version}",
)


class State(TypedDict):
    usecases: UseCases
    worker: IWorker


class Lifespan:
    __slots__ = ["ctx"]

    def __init__(self):
        # instantiate database synchronously to correctly set context vars
        self.ctx = AppContext(config)

    @contextlib.asynccontextmanager
    async def __call__(self, app: FastAPI) -> AsyncIterator[State]:
        async with self.ctx as ctx:
            yield {
                "usecases": ctx.usecases,
                "worker": ctx._infra.worker,
            }


def create_app(
    *,
    lifespan: AbstractAsyncContextManager[State] | None = None,
) -> FastAPI:
    """Create a new app."""
    app = FastAPI(
        title=config.app_name,
        version=config.app_version,
        debug=config.app_debug,
        lifespan=lifespan or Lifespan(),  # type: ignore[arg-type]
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors.allowed_origins,
        allow_methods=config.cors.allowed_methods,
        allow_headers=config.cors.allowed_headers,
    )

    app.include_router(router)

    app.add_exception_handler(
        exceptions.APIError, exceptions.api_error_exception_handler,
    )

    return app


app = create_app()
