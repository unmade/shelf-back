from __future__ import annotations

import enum
from typing import TYPE_CHECKING, Self

import edgedb

from app.app.files.domain import File, FileMember
from app.app.files.repositories import IFileMemberRepository
from app.app.users.domain import User

if TYPE_CHECKING:
    from app.app.files.domain.file_member import FileMemberPermissions
    from app.infrastructure.database.edgedb.typedefs import EdgeDBAnyConn, EdgeDBContext

__all__ = ["FileMemberRepository"]


class PermissionFlag(enum.IntFlag):
    can_view = enum.auto()
    can_download = enum.auto()
    can_upload = enum.auto()
    can_move = enum.auto()
    can_delete = enum.auto()

    @classmethod
    def dump(cls, value: FileMemberPermissions) -> Self:
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
        return flag

    @classmethod
    def load(cls, value: int) -> FileMemberPermissions:
        return FileMember.Permissions(
            can_view=bool(cls.can_view & value),
            can_download=bool(cls.can_download & value),
            can_upload=bool(cls.can_upload & value),
            can_move=bool(cls.can_move & value),
            can_delete=bool(cls.can_delete & value),
        )


def _from_db(obj) -> FileMember:
    return FileMember(
        file_id=str(obj.file.id),
        access_level=FileMember.AccessLevel.editor,
        permissions=PermissionFlag.load(obj.permissions),
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

    async def list_all(self, file_id: str) -> list[FileMember]:
        query = """
            SELECT
                FileMember {
                    permissions,
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
                    permissions := <int16>$permissions,
                }
            ) { permissions, file: { id }, user: { id, username } }
        """

        try:
            obj = await self.conn.query_required_single(
                query,
                file_id=entity.file_id,
                permissions=PermissionFlag.dump(entity.permissions).value,
                user_id=entity.user.id,
            )
        except edgedb.MissingRequiredError as exc:
            if "missing value for required link 'user'" in str(exc):
                raise User.NotFound() from exc
            raise File.NotFound() from exc
        except edgedb.ConstraintViolationError as exc:
            raise FileMember.AlreadyExists() from exc

        return _from_db(obj)
