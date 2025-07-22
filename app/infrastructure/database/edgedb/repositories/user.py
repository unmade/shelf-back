from __future__ import annotations

from typing import TYPE_CHECKING, Unpack, cast, get_type_hints

import gel

from app.app.users.domain import User
from app.app.users.repositories import IUserRepository
from app.app.users.repositories.user import GetKwargs, UserUpdate
from app.infrastructure.database.edgedb import autocast

if TYPE_CHECKING:
    from uuid import UUID

    from app.infrastructure.database.edgedb.typedefs import EdgeDBAnyConn, EdgeDBContext

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

    async def exists_with_email(self, email: str) -> bool:
        query = """
            SELECT EXISTS(
                SELECT
                    User
                FILTER
                    .email = <str>$email
            )
        """
        return cast(bool, await self.conn.query_required_single(query, email=email))

    async def get(self, **fields: Unpack[GetKwargs]) -> User:
        assert fields, "One of the fields must be provided"

        hints = get_type_hints(GetKwargs)

        filter_clause = [
            f".{key} = {autocast.autocast(hints[key])}${key}"
            for key in fields
        ]

        query = f"""
            SELECT
                User {{
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
                }}
            FILTER
                {" AND ".join(filter_clause)}
            LIMIT 1
        """

        try:
            obj = await self.conn.query_required_single(query, **fields)
        except gel.NoDataError as exc:
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
        except gel.ConstraintViolationError as exc:
            message = f"Username '{user.username}' is taken"
            raise User.AlreadyExists(message) from exc

        return user.model_copy(update={"id": obj.id})

    async def update(self, user_id: UUID, **fields: Unpack[UserUpdate]) -> User:
        assert fields, "`fields` must have at least one value"
        hints = get_type_hints(UserUpdate)
        statements = [
            f"{key} := {autocast.autocast(hints[key])}${key}"
            for key in fields
        ]
        query = f"""
            SELECT (
                UPDATE
                    User
                FILTER
                    .id = <uuid>$user_id
                SET {{
                    {','.join(statements)}
                }}
            ) {{
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
            }}
        """
        obj = await self.conn.query_required_single(
            query, user_id=user_id, **fields
        )
        return _from_db(obj)
