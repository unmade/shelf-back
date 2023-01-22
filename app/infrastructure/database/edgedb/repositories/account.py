from __future__ import annotations

from typing import TYPE_CHECKING

import edgedb

from app import crud, errors
from app.app.repositories import IAccountRepository
from app.domain.entities import Account

if TYPE_CHECKING:
    from app.typedefs import StrOrUUID

__all__ = ["AccountRepository"]

class AccountRepository(IAccountRepository):
    def __init__(self, db_context):
        self.db_context = db_context

    @property
    def conn(self):
        return self.db_context.get()

    async def get_by_user_id(self, user_id: StrOrUUID) -> Account:
        query = """
            SELECT Account {
                id, email, first_name, last_name, storage_quota, created_at, user: {
                    username
                }
            }
            FILTER
                .user.id = <uuid>$user_id
            LIMIT 1
        """
        try:
            obj = await self.conn.query_required_single(query, user_id=user_id)
        except edgedb.NoDataError as exc:
            message = f"No account for user with id: {user_id}"
            raise errors.UserNotFound(message) from exc

        return Account.construct(
            id=obj.id,
            username=obj.user.username,
            email=obj.email,
            first_name=obj.first_name,
            last_name=obj.last_name,
            storage_quota=obj.storage_quota,
            created_at=obj.created_at,
        )

    async def save(self, account: Account) -> Account:
        created_account = await crud.account.create(
            self.conn,
            username=account.username,
            email=account.email,
            first_name=account.first_name,
            last_name=account.last_name,
            storage_quota=account.storage_quota,
            created_at=account.created_at,
        )
        return Account.construct(
            id=created_account.id,
            username=account.username,
            email=account.email,
            first_name=account.first_name,
            last_name=account.last_name,
            storage_quota=account.storage_quota,
            created_at=account.created_at,
        )
