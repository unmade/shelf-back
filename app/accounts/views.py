from __future__ import annotations

from fastapi import APIRouter, Depends

from app.auth.deps import get_current_user
from app.auth.models import User

from .schemas import Account

router = APIRouter()


@router.get("/me", response_model=Account)
def get_account_me(curr_user: User = Depends(get_current_user)):
    return curr_user
