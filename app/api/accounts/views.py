from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api import deps
from app.infrastructure.provider import Service

from .schemas import (
    AccountSchema,
    GetAccountSpaceUsageResponse,
)

router = APIRouter()


@router.get("/get_current")
async def get_current(
    user_id: str = Depends(deps.current_user_id),
    services: Service = Depends(deps.services),
) -> AccountSchema:
    """Get account information for a current user."""
    # normally, we would re-raised UserNotFound error, but if some user,
    # doesn't have an account, then it is data integrity error, so fail miserably.
    return AccountSchema.from_entity(
        await services.user.get_account(user_id)
    )


@router.get("/get_space_usage")
async def get_space_usage(
    user_id: str = Depends(deps.current_user_id),
    services: Service = Depends(deps.services),
) -> GetAccountSpaceUsageResponse:
    """Get the space usage information for the current account."""
    account = await services.user.get_account(user_id)
    used = await services.namespace.get_space_used_by_owner_id(user_id)
    return GetAccountSpaceUsageResponse(used=used, quota=account.storage_quota)
