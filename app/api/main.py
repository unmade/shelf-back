from __future__ import annotations

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


def create_app() -> FastAPI:
    """Create a new app."""
    app = FastAPI(
        title=config.APP_NAME,
        version=config.APP_VERSION,
        debug=config.APP_DEBUG,
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

    database = _create_database()
    app.state.provider = Provider(
        database=database,
        storage=_create_storage(),
    )

    @app.on_event("shutdown")
    async def close_db_client():
        await database.shutdown()  # pragma: no cover

    return app


def _create_database():  # pragma: no cover
    return EdgeDBDatabase(
        dsn=config.DATABASE_DSN,
        max_concurrency=4,
        tls_ca_file=config.DATABASE_TLS_CA_FILE,
        tls_security=config.DATABASE_TLS_SECURITY,
    )


def _create_storage():  # pragma: no cover
    if config.STORAGE_TYPE == config.StorageType.s3:
        return S3Storage(
            location=config.STORAGE_LOCATION,
        )
    return FileSystemStorage(location=config.STORAGE_LOCATION)


app = create_app()
