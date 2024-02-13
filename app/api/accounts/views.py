from fastapi import APIRouter

from app.api.deps import CurrentUserDeps, UseCasesDeps
from app.app.users.domain import User
from app.app.users.services.user import (
    EmailUpdateAlreadyStarted,
    EmailUpdateNotStarted,
    OTPCodeAlreadySent,
)
from app.app.users.usecases.user import EmailUpdateLimitReached
from app.cache import cache

from . import exceptions
from .schemas import (
    ChangeEmailCompleteRequest,
    ChangeEmailCompleteResponse,
    ChangeEmailStartRequest,
    CurrentAccountSchema,
    GetAccountSpaceUsageResponse,
    VerifyEmailCompleteRequest,
    VerifyEmailCompleteResponse,
)

router = APIRouter()


@router.post("/change_email/complete")
@cache.rate_limit(
    key="change_email:{user.id}",
    limit=5,
    period="30m",
    ttl="30m",
)
async def change_email_complete(
    payload: ChangeEmailCompleteRequest,
    user: CurrentUserDeps,
    usecases: UseCasesDeps,
) -> ChangeEmailCompleteResponse:
    """Completes the process of updating user email."""
    try:
        completed = await usecases.user.change_email_complete(user.id, payload.code)
    except EmailUpdateNotStarted as exc:
        raise exceptions.EmailUpdateNotStarted() from exc
    return ChangeEmailCompleteResponse(completed=completed)


@router.post("/change_email/resend_code")
@cache.rate_limit(
    key="change_email:{user.id}:send_code",
    limit=6,
    period="30m",
    ttl="30m",
)
async def change_email_resend_code(
    user: CurrentUserDeps,
    usecases: UseCasesDeps,
) -> None:
    """Resends verification to the new email."""
    try:
        await usecases.user.change_email_resend_code(user.id)
    except OTPCodeAlreadySent as exc:
        raise exceptions.OTPCodeAlreadySent() from exc
    except EmailUpdateNotStarted as exc:
        raise exceptions.EmailUpdateNotStarted() from exc


@router.post("/change_email/start")
@cache.rate_limit(
    key="change_email:{user.id}",
    limit=5,
    period="30m",
    ttl="30m",
)
async def change_email_start(
    payload: ChangeEmailStartRequest,
    user: CurrentUserDeps,
    usecases: UseCasesDeps,
) -> None:
    """
    Starts the process of updating user email and sends the verification code to the
    new email."""
    try:
        await usecases.user.change_email_start(user.id, payload.email)
    except User.AlreadyExists as exc:
        raise exceptions.EmailAlreadyTaken() from exc
    except EmailUpdateAlreadyStarted as exc:
        raise exceptions.EmailUpdateStarted() from exc
    except EmailUpdateLimitReached as exc:
        raise exceptions.EmailUpdateLimitReached() from exc


@router.get("/get_current")
async def get_current_account(
    user: CurrentUserDeps,
) -> CurrentAccountSchema:
    """Get account information for a current user."""
    return CurrentAccountSchema.from_entity(user=user)


@router.get("/get_space_usage")
async def get_space_usage(
    user: CurrentUserDeps,
    usecases: UseCasesDeps,
) -> GetAccountSpaceUsageResponse:
    """Get the space usage information for the current account."""
    space_usage = await usecases.user.get_account_space_usage(user.id)
    return GetAccountSpaceUsageResponse(used=space_usage.used, quota=space_usage.quota)


@router.post("/verify_email/send_code")
@cache.rate_limit(
    key="verify_email:{user.id}:send_code",
    limit=6,
    period="30m",
    ttl="30m",
)
async def verify_email_send_code(
    user: CurrentUserDeps,
    usecases: UseCasesDeps,
) -> None:
    """Sends a verification code to the user email."""
    try:
        await usecases.user.verify_email_send_code(user.id)
    except OTPCodeAlreadySent as exc:
        raise exceptions.OTPCodeAlreadySent() from exc
    except User.EmailAlreadyVerified as exc:
        raise exceptions.UserEmailAlreadyVerified() from exc
    except User.EmailIsMissing as exc:
        raise exceptions.UserEmailIsMissing() from exc


@router.post("/verify_email/complete")
@cache.rate_limit(
    key="verify_email:{user.id}",
    limit=5,
    period="30m",
    ttl="30m",
)
async def verify_email_complete(
    payload: VerifyEmailCompleteRequest,
    user: CurrentUserDeps,
    usecases: UseCasesDeps,
) -> VerifyEmailCompleteResponse:
    """Verifies current user email."""
    completed = await usecases.user.verify_email_complete(user.id, payload.code)
    return VerifyEmailCompleteResponse(completed=completed)
