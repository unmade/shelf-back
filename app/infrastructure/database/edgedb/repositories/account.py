from __future__ import annotations

from typing import TYPE_CHECKING

import edgedb

from app.app.users.domain import Account, User
from app.app.users.repositories import IAccountRepository

if TYPE_CHECKING:
    from app.infrastructure.database.edgedb.typedefs import EdgeDBAnyConn, EdgeDBContext
    from app.typedefs import StrOrUUID

__all__ = ["AccountRepository"]


def _from_db(obj) -> Account:
    return Account(
        id=obj.id,
        user_id=obj.user.id,
        storage_quota=obj.storage_quota,
    )


class AccountRepository(IAccountRepository):
    def __init__(self, db_context: EdgeDBContext):
        self.db_context = db_context

    @property
    def conn(self) -> EdgeDBAnyConn:
        return self.db_context.get()

    async def get_by_user_id(self, user_id: StrOrUUID) -> Account:
        query = """
            SELECT Account {
                id,  storage_quota, user: { id }
            }
            FILTER
                .user.id = <uuid>$user_id
            LIMIT 1
        """
        try:
            obj = await self.conn.query_required_single(query, user_id=user_id)
        except edgedb.NoDataError as exc:
            message = f"No account for user with id: {user_id}"
            raise User.NotFound(message) from exc

        return _from_db(obj)

    async def save(self, account: Account) -> Account:
        query = """
            SELECT (
                INSERT Account {
                    storage_quota := <OPTIONAL int64>$storage_quota,
                    user := (
                        SELECT
                            User
                        FILTER
                            .id = <uuid>$user_id
                        LIMIT 1
                    )
                }
            ) { id }
        """

        obj = await self.conn.query_required_single(
            query,
            user_id=account.user_id,
            storage_quota=account.storage_quota,
        )

        return account.model_copy(update={"id": obj.id})
