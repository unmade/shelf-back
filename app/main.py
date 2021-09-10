from __future__ import annotations

from cashews import cache
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import api, config, db


def create_app() -> FastAPI:
    """Create a new app."""
    app = FastAPI(
        title=config.APP_NAME,
        version=config.APP_VERSION or "0.1.0",
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
    async def create_pool():
        await db.create_pool()

    @app.on_event("shutdown")
    async def close_pool():
        await db.close_pool()

    return app


cache.setup(config.CACHE_BACKEND_DSN)
app = create_app()
