from fastapi import APIRouter
from fastapi.responses import ORJSONResponse

from .accounts.views import router as accounts
from .auth.views import router as auth
from .features.views import router as features
from .files.views import router as files
from .photos import router as photos
from .sharing.views import router as sharing
from .users.views import router as users

router = APIRouter(default_response_class=ORJSONResponse)

router.include_router(accounts, prefix="/accounts", tags=["accounts"])
router.include_router(auth, prefix="/auth", tags=["auth"])
router.include_router(features, prefix="/features", tags=["features"])
router.include_router(files, prefix="/files", tags=["files"])
router.include_router(photos, prefix="/photos")
router.include_router(sharing, prefix="/sharing", tags=["sharing"])
router.include_router(users, prefix="/users", tags=["users"])
