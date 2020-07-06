from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api import deps
from app.models.user import User

from .schemas import UserMe

router = APIRouter()


@router.get("/me", response_model=UserMe)
def get_user_me(curr_user: User = Depends(deps.current_user)):
    return curr_user
