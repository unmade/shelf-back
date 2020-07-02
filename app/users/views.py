from __future__ import annotations

from fastapi import APIRouter, Depends

from app.auth.deps import get_current_user

from .models import User
from .schemas import UserMe

router = APIRouter()


@router.get("/me", response_model=UserMe)
def get_user_me(curr_user: User = Depends(get_current_user)):
    return curr_user
