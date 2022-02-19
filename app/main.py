from __future__ import annotations

import sentry_sdk
from cashews import cache
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sentry_sdk.integrations.asgi import SentryAsgiMiddleware

from app import api, config, db


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
        api.exceptions.APIError, api.exceptions.api_error_exception_handler
    )

    @app.on_event("startup")
    async def init_db_client():
        await db.init_client()

    @app.on_event("shutdown")
    async def close_db_client():
        await db.close_client()

    sentry_sdk.init(
        config.SENTRY_DSN,
        environment=config.SENTRY_ENV,
        release=f"shelf@{app.version}",
    )
    app.add_middleware(SentryAsgiMiddleware)

    return app


cache.setup(config.CACHE_BACKEND_DSN)
app = create_app()
