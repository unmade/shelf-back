from __future__ import annotations

import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import api, config, db

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

    app.include_router(api.router)

    app.add_exception_handler(
        ExceptionGroup,  # noqa: F821
        api.exceptions.api_error_exception_group_handler,
    )
    app.add_exception_handler(
        api.exceptions.APIError, api.exceptions.api_error_exception_handler,
    )

    @app.on_event("startup")
    async def init_db_client():
        await db.init_client()

    @app.on_event("shutdown")
    async def close_db_client():
        await db.close_client()

    return app


app = create_app()
