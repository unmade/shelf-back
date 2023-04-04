from __future__ import annotations

import contextlib
from typing import AsyncContextManager, AsyncIterator, TypedDict

import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import FileSystemStorageConfig, S3StorageConfig, config
from app.infrastructure.database.edgedb.db import EdgeDBDatabase
from app.infrastructure.provider import Provider
from app.infrastructure.storage import FileSystemStorage, S3Storage

from . import exceptions, router

sentry_sdk.init(
    config.sentry.dsn,
    environment=config.sentry.environment,
    release=f"shelf@{config.app_version}",
)


class State(TypedDict):
    provider: Provider


class Lifespan:
    __slots__ = ["database", "storage"]

    def __init__(self):
        # instantiate database synchronously to correctly set context vars
        self.database = self._create_database()
        self.storage = self._create_storage()

    @contextlib.asynccontextmanager
    async def __call__(self, app: FastAPI) -> AsyncIterator[State]:
        async with self.database as database:
            provider = Provider(
                database=database,
                storage=self.storage,
            )
            yield {"provider": provider}

    @staticmethod
    def _create_database():  # pragma: no cover
        return EdgeDBDatabase(config=config.database)

    @staticmethod
    def _create_storage():  # pragma: no cover
        if isinstance(config.storage, S3StorageConfig):
            return S3Storage(config.storage)
        if isinstance(config.storage, FileSystemStorageConfig):
            return FileSystemStorage(config.storage)
        return None


def create_app(*, lifespan: AsyncContextManager[State] | None = None) -> FastAPI:
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
