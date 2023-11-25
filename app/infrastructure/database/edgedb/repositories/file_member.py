from __future__ import annotations

import enum
from typing import TYPE_CHECKING, Self

import edgedb

from app.app.files.domain import File, FileMember
from app.app.files.repositories import IFileMemberRepository
from app.app.files.repositories.file_member import FileMemberUpdate
from app.app.users.domain import User

if TYPE_CHECKING:
    from uuid import UUID

    from app.app.files.domain.file_member import FileMemberActions
    from app.infrastructure.database.edgedb.typedefs import EdgeDBAnyConn, EdgeDBContext

__all__ = ["FileMemberRepository"]


class ActionFlag(enum.IntFlag):
    # new values should be added stricly to the end
    can_view = enum.auto()
    can_download = enum.auto()
    can_upload = enum.auto()
    can_move = enum.auto()
    can_delete = enum.auto()
    can_reshare = enum.auto()
    can_unshare = enum.auto()

    @classmethod
    def dump(cls, value: FileMemberActions) -> Self:
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
        return flag

    @classmethod
    def load(cls, value: int) -> FileMemberActions:
        return FileMember.Actions(
            can_view=bool(cls.can_view & value),
            can_download=bool(cls.can_download & value),
            can_upload=bool(cls.can_upload & value),
            can_move=bool(cls.can_move & value),
            can_delete=bool(cls.can_delete & value),
            can_reshare=bool(cls.can_reshare & value),
            can_unshare=bool(cls.can_unshare & value),
        )


def _from_db(obj) -> FileMember:
    return FileMember(
        file_id=obj.file.id,
        actions=ActionFlag.load(obj.actions),
        user=FileMember.User(
            id=obj.user.id,
            username=obj.user.username,
        )
    )


class FileMemberRepository(IFileMemberRepository):
    def __init__(self, db_context: EdgeDBContext):
        self.db_context = db_context

    @property
    def conn(self) -> EdgeDBAnyConn:
        return self.db_context.get()

    async def delete(self, file_id: UUID, user_id: UUID) -> None:
        query = """
            DELETE
                FileMember
            FILTER
                .file.id = <uuid>$file_id
                AND
                .user.id = <uuid>$user_id
        """

        await self.conn.query(query, file_id=file_id, user_id=user_id)

    async def get(self, file_id: UUID, user_id: UUID) -> FileMember:
        query = """
            SELECT
                FileMember {
                    actions,
                    file: { id },
                    user: { id, username },
                }
            FILTER
                .file.id = <uuid>$file_id
                AND
                .user.id = <uuid>$user_id
            LIMIT 1
        """

        try:
            obj = await self.conn.query_required_single(
                query,
                file_id=file_id,
                user_id=user_id,
            )
        except edgedb.NoDataError as exc:
            raise FileMember.NotFound() from exc

        return _from_db(obj)

    async def list_all(self, file_id: UUID) -> list[FileMember]:
        query = """
            SELECT
                FileMember {
                    actions,
                    file: { id },
                    user: { id, username },
                }
            FILTER
                .file.id = <uuid>$file_id
        """

        objs = await self.conn.query(query, file_id=file_id)
        return [_from_db(obj) for obj in objs]

    async def save(self, entity: FileMember) -> FileMember:
        query = """
            WITH
                file := (SELECT File FILTER .id = <uuid>$file_id),
                user := (SELECT User FILTER .id = <uuid>$user_id),
            SELECT (
                INSERT FileMember {
                    file := file,
                    user := user,
                    actions := <int16>$actions,
                }
            ) { actions, file: { id }, user: { id, username } }
        """

        try:
            obj = await self.conn.query_required_single(
                query,
                file_id=entity.file_id,
                user_id=entity.user.id,
                actions=ActionFlag.dump(entity.actions).value,
            )
        except edgedb.MissingRequiredError as exc:
            if "missing value for required link 'user'" in str(exc):
                raise User.NotFound() from exc
            raise File.NotFound() from exc
        except edgedb.ConstraintViolationError as exc:
            raise FileMember.AlreadyExists() from exc

        return _from_db(obj)

    async def update(self, entity: FileMember, fields: FileMemberUpdate) -> FileMember:
        actions = ActionFlag.dump(fields["actions"])
        query = """
            SELECT (
                UPDATE
                    FileMember
                FILTER
                    .file.id = <uuid>$file_id
                    AND
                    .user.id = <uuid>$user_id
                SET {
                    actions := <int16>$actions
                }
            ) { actions, file: { id }, user: { id, username } }
        """

        try:
            obj = await self.conn.query_required_single(
                query,
                file_id=entity.file_id,
                user_id=entity.user.id,
                actions=actions,
            )
        except edgedb.NoDataError as exc:
            raise FileMember.NotFound() from exc

        return _from_db(obj)
