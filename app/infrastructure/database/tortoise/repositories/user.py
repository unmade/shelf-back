from __future__ import annotations

from typing import TYPE_CHECKING, Unpack

from tortoise.exceptions import DoesNotExist, IntegrityError

from app.app.users.domain import User
from app.app.users.repositories import IUserRepository
from app.app.users.repositories.user import GetKwargs, UserUpdate
from app.infrastructure.database.tortoise import models

if TYPE_CHECKING:
    from uuid import UUID

__all__ = ["UserRepository"]


def _from_db(obj: models.User) -> User:
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
    async def exists_with_email(self, email: str) -> bool:
        return await models.User.filter(email=email).exists()

    async def get(self, **fields: Unpack[GetKwargs]) -> User:
        assert fields, "One of the fields must be provided"
        try:
            obj = await models.User.get(**fields)
        except DoesNotExist as exc:
            raise User.NotFound() from exc
        return _from_db(obj)

    async def save(self, user: User) -> User:
        obj = models.User(
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

        try:
            await obj.save()
        except IntegrityError as exc:
            message = f"Username '{user.username}' is taken"
            raise User.AlreadyExists(message) from exc

        return user.model_copy(update={"id": obj.id})

    async def update(self, user_id: UUID, **fields: Unpack[UserUpdate]) -> User:
        assert fields, "`fields` must have at least one value"
        await models.User.filter(id=user_id).update(**fields)
        obj = await models.User.get(id=user_id)
        return _from_db(obj)
