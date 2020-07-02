import pathlib

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app import accounts, auth, config, errors

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth.views.router, prefix="/auth")
app.include_router(accounts.views.router, prefix="/accounts")
app.mount("/static", StaticFiles(directory=config.STATIC_DIR), name="static")
app.add_exception_handler(errors.APIError, errors.api_error_exception_handler)


@app.get("/files")
def read_root(path: str = None):
    static_dir = pathlib.Path(config.STATIC_DIR)
    curr_path = static_dir if path is None else static_dir.joinpath(path)
    return {
        "directory": {
            "name": curr_path.name if curr_path != static_dir else "home",
            "path": curr_path.relative_to(static_dir),
            "folderCount": 0,
            "fileCount": 0,
        },
        "files": [
            {
                "type": "folder" if file.is_dir() else "image",
                "name": file.name,
                "size": file.stat().st_size,
                "modified_at": file.stat().st_mtime,
                "path": str(file.relative_to(curr_path)),
            }
            for file in curr_path.iterdir()
        ],
    }
