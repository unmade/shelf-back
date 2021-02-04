from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api import deps
from app.entities.account import Account

from .schemas import AccountMe

router = APIRouter()


@router.get("/me", response_model=AccountMe)
def get_user_me(account: Account = Depends(deps.current_account)):
    """Returns account information for current user."""
    return account
