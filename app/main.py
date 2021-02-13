from cashews import cache
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app import api, config, db


def create_app():
    app = FastAPI(
        title=config.APP_NAME,
        version=config.APP_VERSION or "0.1.0",
        debug=config.APP_DEBUG,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api.router)

    app.mount("/static", StaticFiles(directory=config.STATIC_DIR), name="static")
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


cache.setup("mem://")
app = create_app()
