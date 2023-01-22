from __future__ import annotations

from typing import TYPE_CHECKING

import edgedb

from app import errors
from app.app.repositories import IUserRepository
from app.domain.entities import User

if TYPE_CHECKING:
    pass

__all__ = ["UserRepository"]


class UserRepository(IUserRepository):
    def __init__(self, db_context):
        self.db_context = db_context

    @property
    def conn(self):
        return self.db_context.get()

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
