from fastapi import APIRouter

from .accounts.views import router as accounts
from .auth.views import router as auth
from .files.views import router as files

router = APIRouter()
router.include_router(accounts, prefix="/accounts", tags=["accounts"])
router.include_router(auth, prefix="/auth", tags=["auth"])
router.include_router(files, prefix="/files", tags=["files"])
