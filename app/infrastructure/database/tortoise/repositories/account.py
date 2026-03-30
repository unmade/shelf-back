from __future__ import annotations

from typing import TYPE_CHECKING

from tortoise.exceptions import DoesNotExist

from app.app.users.domain import Account, User
from app.app.users.repositories import IAccountRepository
from app.infrastructure.database.tortoise import models

if TYPE_CHECKING:
    from app.typedefs import StrOrUUID

__all__ = ["AccountRepository"]


class AccountRepository(IAccountRepository):
    async def get_by_user_id(self, user_id: StrOrUUID) -> Account:
        try:
            obj = await models.Account.get(user_id=user_id)
        except DoesNotExist as exc:
            raise User.NotFound(f"No account for user with id: {user_id}") from exc
        return Account(
            id=obj.id,
            user_id=obj.user_id,  # type: ignore[attr-defined]
            storage_quota=obj.storage_quota
        )

    async def save(self, account: Account) -> Account:
        obj = models.Account(
            user_id=account.user_id,
            storage_quota=account.storage_quota,
        )
        await obj.save()
        return account.model_copy(update={"id": obj.id})
