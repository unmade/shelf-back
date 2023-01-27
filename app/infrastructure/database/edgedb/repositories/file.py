from __future__ import annotations

from typing import TYPE_CHECKING, Iterable
from uuid import UUID

import edgedb

from app import crud, errors
from app.app.repositories import IFileRepository
from app.domain.entities import File

if TYPE_CHECKING:
    from app.entities import File as LegacyFile
    from app.infrastructure.database.edgedb.typedefs import EdgeDBAnyConn, EdgeDBContext
    from app.typedefs import StrOrPath

__all__ = ["FileRepository"]


def _from_db(ns_path: str, obj: LegacyFile) -> File:
    return File(
        id=UUID(obj.id),
        ns_path=ns_path,
        name=obj.name,
        path=obj.path,
        size=obj.size,
        mtime=obj.mtime,
        mediatype=obj.mediatype,
    )


class FileRepository(IFileRepository):
    def __init__(self, db_context: EdgeDBContext):
        self.db_context = db_context

    @property
    def conn(self) -> EdgeDBAnyConn:
        return self.db_context.get()

    async def get_by_path(self, ns_path: StrOrPath, path: StrOrPath) -> File:
        obj = await crud.file.get(self.conn, ns_path, path)
        return _from_db(str(ns_path), obj)

    async def get_by_path_batch(
        self, ns_path: StrOrPath, paths: Iterable[StrOrPath],
    ) -> list[File]:
        files = await crud.file.get_many(self.conn,namespace=ns_path, paths=paths)
        return [_from_db(str(ns_path), file) for file in files]

    async def incr_size_batch(
        self, ns_path: StrOrPath, paths: Iterable[StrOrPath], value: int
    ) -> None:
        return await crud.file.inc_size_batch(self.conn, ns_path, paths, value)

    async def next_path(self, ns_path: StrOrPath, path: StrOrPath) -> str:
        return await crud.file.next_path(self.conn, ns_path, path)

    async def save(self, file: File) -> File:
        query = """
            SELECT (
                INSERT File {
                    name := <str>$name,
                    path := <str>$path,
                    size := <int64>$size,
                    mtime := <float64>$mtime,
                    mediatype := (
                        INSERT MediaType {
                            name := <str>$mediatype
                        }
                        UNLESS CONFLICT ON .name
                        ELSE (
                            SELECT
                                MediaType
                            FILTER
                                .name = <str>$mediatype
                        )
                    ),
                    namespace := (
                        SELECT
                            Namespace
                        FILTER
                            .path = <str>$namespace
                        LIMIT 1
                    ),
                }
            ) { id, name, path, size, mtime, mediatype: { name } }
        """

        params = {
            "name": file.name,
            "path": file.path,
            "size": file.size,
            "mtime": file.mtime,
            "mediatype": file.mediatype,
            "namespace": str(file.ns_path),
        }

        try:
            obj = await self.conn.query_required_single(query, **params)
        except edgedb.ConstraintViolationError as exc:
            raise errors.FileAlreadyExists() from exc

        return file.copy(update={"id": obj.id})
