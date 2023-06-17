from __future__ import annotations

from typing import TYPE_CHECKING

import edgedb

from app.app.files.domain import File, FileMember
from app.app.files.repositories import IFileMemberRepository
from app.app.users.domain import User

if TYPE_CHECKING:
    from app.infrastructure.database.edgedb.typedefs import EdgeDBAnyConn, EdgeDBContext

__all__ = ["FileMemberRepository"]


def _from_db(obj) -> FileMember:
    return FileMember(
        file_id=str(obj.file.id),
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
                    permissions := 0,
                }
            ) { file: { id }, user: { id, username } }
        """

        try:
            obj = await self.conn.query_required_single(
                query,
                file_id=entity.file_id,
                user_id=entity.user.id,
            )
        except edgedb.MissingRequiredError as exc:
            if "missing value for required link 'user'" in str(exc):
                raise User.NotFound() from exc
            raise File.NotFound() from exc
        except edgedb.ConstraintViolationError as exc:
            raise FileMember.AlreadyExists() from exc

        return _from_db(obj)
