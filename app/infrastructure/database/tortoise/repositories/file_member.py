from __future__ import annotations

import enum
from typing import TYPE_CHECKING

from tortoise.exceptions import DoesNotExist, IntegrityError

from app.app.files.domain import File, FileMember
from app.app.files.repositories import IFileMemberRepository
from app.app.files.repositories.file_member import FileMemberUpdate
from app.app.users.domain import User
from app.infrastructure.database.tortoise import models

if TYPE_CHECKING:
    from collections.abc import Iterable
    from uuid import UUID

    from app.app.files.domain.file_member import FileMemberActions

__all__ = ["FileMemberRepository"]


class ActionFlag(enum.IntFlag):
    # new values should be added strictly to the end
    can_view = enum.auto()
    can_download = enum.auto()
    can_upload = enum.auto()
    can_move = enum.auto()
    can_delete = enum.auto()
    can_reshare = enum.auto()
    can_unshare = enum.auto()

    @classmethod
    def dump(cls, value: FileMemberActions) -> int:
        flag = cls(0)
        if value.can_view:
            flag |= cls.can_view
        if value.can_download:
            flag |= cls.can_download
        if value.can_upload:
            flag |= cls.can_upload
        if value.can_move:
            flag |= cls.can_move
        if value.can_delete:
            flag |= cls.can_delete
        if value.can_reshare:
            flag |= cls.can_reshare
        if value.can_unshare:
            flag |= cls.can_unshare

        if flag == cls(-1):
            return -1
        return flag.value

    @classmethod
    def load(cls, value: int) -> FileMemberActions:
        if value == -1:
            return FileMember.OWNER

        return FileMember.Actions(
            can_view=bool(cls.can_view & value),
            can_download=bool(cls.can_download & value),
            can_upload=bool(cls.can_upload & value),
            can_move=bool(cls.can_move & value),
            can_delete=bool(cls.can_delete & value),
            can_reshare=bool(cls.can_reshare & value),
            can_unshare=bool(cls.can_unshare & value),
        )


def _from_db(obj: models.FileMember) -> FileMember:
    return FileMember(
        file_id=obj.file_id,  # type: ignore[attr-defined]
        actions=ActionFlag.load(obj.actions),
        created_at=obj.created_at,
        user=FileMember.User(
            id=obj.user.id,
            username=obj.user.username,
        ),
    )


class FileMemberRepository(IFileMemberRepository):
    async def delete(self, file_id: UUID, user_id: UUID) -> None:
        await models.FileMember.filter(
            file_id=file_id, user_id=user_id
        ).delete()

    async def get(self, file_id: UUID, user_id: UUID) -> FileMember:
        try:
            obj = await (
                models.FileMember
                .filter(file_id=file_id, user_id=user_id)
                .select_related("user")
                .get()
            )
        except DoesNotExist as exc:
            raise FileMember.NotFound() from exc
        return _from_db(obj)

    async def list_by_file_id_batch(
        self, file_ids: Iterable[UUID]
    ) -> list[FileMember]:
        objs = await (
            models.FileMember
            .filter(file_id__in=list(file_ids))
            .select_related("user")
            .order_by("created_at")
        )
        return [_from_db(obj) for obj in objs]

    async def list_by_user_id(
        self, user_id: UUID, *, offset: int = 0, limit: int = 25
    ) -> list[FileMember]:
        objs = await (
            models.FileMember
            .filter(user_id=user_id)
            .select_related("user")
            .offset(offset)
            .limit(limit)
        )
        return [_from_db(obj) for obj in objs]

    async def save(self, entity: FileMember) -> FileMember:
        try:
            obj = await models.FileMember.create(
                file_id=entity.file_id,
                user_id=entity.user.id,
                actions=ActionFlag.dump(entity.actions),
                created_at=entity.created_at,
            )
        except IntegrityError as exc:
            err_msg = str(exc).lower()
            if "unique" in err_msg:
                raise FileMember.AlreadyExists() from exc
            if not await models.User.filter(id=entity.user.id).exists():
                raise User.NotFound() from exc
            raise File.NotFound() from exc

        obj = await (
            models.FileMember
            .filter(id=obj.id)
            .select_related("user")
            .get()
        )
        return _from_db(obj)

    async def update(
        self, entity: FileMember, fields: FileMemberUpdate
    ) -> FileMember:
        actions = ActionFlag.dump(fields["actions"])
        updated = await (
            models.FileMember
            .filter(file_id=entity.file_id, user_id=entity.user.id)
            .update(actions=actions)
        )
        if not updated:
            raise FileMember.NotFound()

        obj = await (
            models.FileMember
            .filter(file_id=entity.file_id, user_id=entity.user.id)
            .select_related("user")
            .get()
        )
        return _from_db(obj)
