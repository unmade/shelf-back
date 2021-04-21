from __future__ import annotations

from edgedb import AsyncIOPool
from fastapi import APIRouter, Depends

from app import actions, crud, errors
from app.api import deps
from app.entities import User

from .exceptions import UserAlreadyExists
from .schemas import Account, CreateAccountRequest

router = APIRouter()


@router.post("/create", response_model=Account)
async def create(
    payload: CreateAccountRequest,
    db_pool: AsyncIOPool = Depends(deps.db_pool),
    user: User = Depends(deps.current_user),
):
    """Create new account."""
    try:
        return await actions.create_account(
            db_pool,
            payload.username,
            payload.password,
            email=payload.email,
            first_name=payload.first_name,
            last_name=payload.last_name,
        )
    except errors.UserAlreadyExists as exc:
        raise UserAlreadyExists(str(exc)) from exc


@router.get("/get_current", response_model=Account)
async def get_current(
    db_pool: AsyncIOPool = Depends(deps.db_pool),
    user_id: str = Depends(deps.current_user_id),
):
    """Get account information for a current user."""
    return await crud.account.get(db_pool, user_id)
