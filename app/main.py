from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app import auth, config, errors, files, users


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

    app.include_router(auth.views.router, prefix="/auth")
    app.include_router(files.views.router, prefix="/files")
    app.include_router(users.views.router, prefix="/accounts")

    app.mount("/static", StaticFiles(directory=config.STATIC_DIR), name="static")
    app.add_exception_handler(errors.APIError, errors.api_error_exception_handler)

    return app


app = create_app()
