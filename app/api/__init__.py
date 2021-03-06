from fastapi import APIRouter

from . import exceptions  # noqa
from .auth.views import router as auth_router
from .files.views import router as files_router

router = APIRouter()
router.include_router(auth_router, prefix="/auth", tags=["auth"])
router.include_router(files_router, prefix="/files", tags=["files"])
