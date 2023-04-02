from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import CurrentUserDeps, UseCasesDeps

from .schemas import (
    AccountSchema,
    GetAccountSpaceUsageResponse,
)

router = APIRouter()


@router.get("/get_current")
async def get_current(
    user: CurrentUserDeps,
    usecases: UseCasesDeps,
) -> AccountSchema:
    """Get account information for a current user."""
    # normally, we would re-raised UserNotFound error, but if some user,
    # doesn't have an account, then it is data integrity error, so fail miserably.
    return AccountSchema.from_entity(
        await usecases.user.get_account(user.id)
    )


@router.get("/get_space_usage")
async def get_space_usage(
    user: CurrentUserDeps,
    usecases: UseCasesDeps,
) -> GetAccountSpaceUsageResponse:
    """Get the space usage information for the current account."""
    space_usage = await usecases.user.get_account_space_usage(user.id)
    return GetAccountSpaceUsageResponse(used=space_usage.used, quota=space_usage.quota)
