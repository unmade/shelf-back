from __future__ import annotations

from typing import TYPE_CHECKING

import edgedb

from app import errors
from app.app.repositories import IUserRepository
from app.domain.entities import User

if TYPE_CHECKING:
    from uuid import UUID

    from app.infrastructure.database.edgedb.typedefs import EdgeDBAnyConn, EdgeDBContext
    from app.typedefs import StrOrUUID

__all__ = ["UserRepository"]


class UserRepository(IUserRepository):
    def __init__(self, db_context: EdgeDBContext):
        self.db_context = db_context

    @property
    def conn(self) -> EdgeDBAnyConn:
        return self.db_context.get()

    async def add_bookmark(self, user_id: StrOrUUID, file_id: StrOrUUID) -> None:
        query = """
            UPDATE
                User
            FILTER
                .id = <uuid>$user_id
            SET {
                bookmarks += (
                    SELECT
                        File
                    FILTER
                        .id = <uuid>$file_id
                    LIMIT 1
                )
            }
        """

        try:
            await self.conn.query_required_single(
                query, user_id=user_id, file_id=file_id,
            )
        except edgedb.NoDataError as exc:
            raise errors.UserNotFound(f"No user with id: '{user_id}'") from exc

    async def list_bookmarks(self, user_id: StrOrUUID) -> list[UUID]:
        query = """
            SELECT
                User { bookmarks }
            FILTER
                .id = <uuid>$user_id
            LIMIT 1
        """
        try:
            user = await self.conn.query_required_single(query, user_id=user_id)
        except edgedb.NoDataError as exc:
            raise errors.UserNotFound(f"No user with id: '{user_id}'") from exc

        return [entry.id for entry in user.bookmarks]

    async def remove_bookmark(self, user_id: StrOrUUID, file_id: StrOrUUID) -> None:
        query = """
            UPDATE
                User
            FILTER
                .id = <uuid>$user_id
            SET {
                bookmarks -= (
                    SELECT
                        File
                    FILTER
                        .id = <uuid>$file_id
                    LIMIT 1
                )
            }
        """

        try:
            await self.conn.query_required_single(
                query, user_id=user_id, file_id=file_id
            )
        except edgedb.NoDataError as exc:
            raise errors.UserNotFound() from exc

    async def save(self, user: User) -> User:
        query = """
            SELECT (
                INSERT User {
                    username := <str>$username,
                    password := <str>$password,
                    superuser := <bool>$superuser,
                }
            ) { id, username, superuser }
        """

        try:
            obj = await self.conn.query_required_single(
                query,
                username=user.username,
                password=user.password,
                superuser=user.superuser,
            )
        except edgedb.ConstraintViolationError as exc:
            message = f"Username '{user.username}' is taken"
            raise errors.UserAlreadyExists(message) from exc

        return user.copy(update={"id": obj.id})
