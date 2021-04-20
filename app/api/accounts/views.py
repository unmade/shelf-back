from __future__ import annotations

from edgedb import AsyncIOPool
from fastapi import APIRouter, Depends

from app import crud
from app.api import deps

from .schemas import Account

router = APIRouter()


@router.get("/get_current", response_model=Account)
async def get_current(
    db_pool: AsyncIOPool = Depends(deps.db_pool),
    user_id: str = Depends(deps.current_user_id),
):
    """Get account information for a current user."""
    return await crud.account.get(db_pool, user_id)
