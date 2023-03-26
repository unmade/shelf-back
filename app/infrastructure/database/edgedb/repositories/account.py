from __future__ import annotations

from typing import TYPE_CHECKING

import edgedb

from app.app.users.domain import Account, User
from app.app.users.repositories import IAccountRepository

if TYPE_CHECKING:
    from app.infrastructure.database.edgedb.typedefs import EdgeDBAnyConn, EdgeDBContext
    from app.typedefs import StrOrUUID

__all__ = ["AccountRepository"]


class AccountRepository(IAccountRepository):
    def __init__(self, db_context: EdgeDBContext):
        self.db_context = db_context

    @property
    def conn(self) -> EdgeDBAnyConn:
        return self.db_context.get()

    async def get_by_user_id(self, user_id: StrOrUUID) -> Account:
        query = """
            SELECT Account {
                id, email, first_name, last_name, storage_quota, created_at, user: {
                    id, username
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
            raise User.NotFound(message) from exc

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
        query = """
            SELECT (
                INSERT Account {
                    email := <OPTIONAL str>$email,
                    first_name := <str>$first_name,
                    last_name := <str>$last_name,
                    storage_quota := <OPTIONAL int64>$storage_quota,
                    created_at := <datetime>$created_at,
                    user := (
                        SELECT
                            User
                        FILTER
                            .username = <str>$username
                        LIMIT 1
                    )
                }
            ) { id }
        """
        try:
            obj = await self.conn.query_required_single(
                query,
                username=account.username,
                email=account.email,
                first_name=account.first_name,
                last_name=account.last_name,
                storage_quota=account.storage_quota,
                created_at=account.created_at,
            )
        except edgedb.ConstraintViolationError as exc:
            raise User.AlreadyExists(f"Email '{account.email}' is taken") from exc

        return account.copy(update={"id": obj.id})
