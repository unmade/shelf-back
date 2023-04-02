from __future__ import annotations

import contextlib
from typing import AsyncContextManager, AsyncIterator, TypedDict

import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import config
from app.infrastructure.database.edgedb.db import EdgeDBDatabase
from app.infrastructure.provider import Provider
from app.infrastructure.storage import FileSystemStorage, S3Storage

from . import exceptions, router

sentry_sdk.init(
    config.SENTRY_DSN,
    environment=config.SENTRY_ENV,
    release=f"shelf@{config.APP_VERSION}",
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
        return EdgeDBDatabase(
            dsn=config.DATABASE_DSN,
            max_concurrency=4,
            tls_ca_file=config.DATABASE_TLS_CA_FILE,
            tls_security=config.DATABASE_TLS_SECURITY,
        )

    @staticmethod
    def _create_storage():  # pragma: no cover
        if config.STORAGE_TYPE == config.StorageType.s3:  # noqa: SIM300
            return S3Storage(
                location=config.STORAGE_LOCATION,
            )
        return FileSystemStorage(location=config.STORAGE_LOCATION)


def create_app(*, lifespan: AsyncContextManager[State] | None = None) -> FastAPI:
    """Create a new app."""
    app = FastAPI(
        title=config.APP_NAME,
        version=config.APP_VERSION,
        debug=config.APP_DEBUG,
        lifespan=lifespan or Lifespan(),  # type: ignore[arg-type]
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.CORS_ALLOW_ORIGINS,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router)

    app.add_exception_handler(
        exceptions.APIError, exceptions.api_error_exception_handler,
    )

    return app


app = create_app()
