from __future__ import annotations

from typing import TYPE_CHECKING

import edgedb

from app.app.users.domain import User
from app.app.users.repositories import IUserRepository

if TYPE_CHECKING:
    from uuid import UUID

    from app.infrastructure.database.edgedb.typedefs import EdgeDBAnyConn, EdgeDBContext
    from app.typedefs import StrOrUUID

__all__ = ["UserRepository"]


def _from_db(obj) -> User:
    return User(
        id=obj.id,
        username=obj.username,
        password=obj.password,
        email=obj.email,
        email_verified=obj.email_verified,
        display_name=obj.display_name,
        created_at=obj.created_at,
        last_login_at=obj.last_login_at,
        active=obj.active,
        superuser=obj.superuser,
    )


class UserRepository(IUserRepository):
    def __init__(self, db_context: EdgeDBContext):
        self.db_context = db_context

    @property
    def conn(self) -> EdgeDBAnyConn:
        return self.db_context.get()

    async def get_by_username(self, username: str) -> User:
        query = """
            SELECT
                User {
                    id,
                    username,
                    password,
                    email,
                    email_verified,
                    display_name,
                    created_at,
                    last_login_at,
                    active,
                    superuser,
                }
            FILTER
                .username = <str>$username
            LIMIT 1
        """
        try:
            obj = await self.conn.query_required_single(query, username=username)
        except edgedb.NoDataError as exc:
            raise User.NotFound() from exc
        return _from_db(obj)

    async def get_by_id(self, user_id: StrOrUUID) -> User:
        query = """
            SELECT
                User {
                    id,
                    username,
                    password,
                    email,
                    email_verified,
                    display_name,
                    created_at,
                    last_login_at,
                    active,
                    superuser,
                }
            FILTER
                .id = <uuid>$user_id
        """
        try:
            obj = await self.conn.query_required_single(query, user_id=user_id)
        except edgedb.NoDataError as exc:
            raise User.NotFound() from exc
        return _from_db(obj)

    async def save(self, user: User) -> User:
        query = """
            SELECT (
                INSERT User {
                    username := <str>$username,
                    password := <str>$password,
                    email := <OPTIONAL str>$email,
                    email_verified := <bool>$email_verified,
                    display_name := <str>$display_name,
                    created_at := <datetime>$created_at,
                    last_login_at := <OPTIONAL datetime>$last_login_at,
                    active := <bool>$active,
                    superuser := <bool>$superuser,
                }
            ) { id }
        """

        try:
            obj = await self.conn.query_required_single(
                query,
                username=user.username,
                password=user.password,
                email=user.email,
                email_verified=user.email_verified,
                display_name=user.display_name,
                created_at=user.created_at,
                last_login_at=user.last_login_at,
                active=user.active,
                superuser=user.superuser,
            )
        except edgedb.ConstraintViolationError as exc:
            message = f"Username '{user.username}' is taken"
            raise User.AlreadyExists(message) from exc

        return user.model_copy(update={"id": obj.id})

    async def set_email_verified(self, user_id: UUID, *, verified: bool) -> None:
        query = """
            UPDATE
                User
            FILTER
                .id = <uuid>$user_id
            SET {
                email_verified := <bool>$verified
            }
        """

        await self.conn.query_required_single(query, user_id=user_id, verified=verified)
