from __future__ import annotations

from typing import TYPE_CHECKING, Iterable, cast, get_type_hints

import edgedb

from app import errors
from app.app.repositories import IFileRepository
from app.app.repositories.file import FileUpdate
from app.domain.entities import File
from app.infrastructure.database.edgedb import autocast

if TYPE_CHECKING:
    from app.infrastructure.database.edgedb.typedefs import EdgeDBAnyConn, EdgeDBContext
    from app.typedefs import StrOrPath, StrOrUUID

__all__ = ["FileRepository"]


def _from_db(ns_path: str, obj) -> File:
    return File(
        id=obj.id,
        ns_path=ns_path,
        name=obj.name,
        path=obj.path,
        size=obj.size,
        mtime=obj.mtime,
        mediatype=obj.mediatype.name,
    )


class FileRepository(IFileRepository):
    def __init__(self, db_context: EdgeDBContext):
        self.db_context = db_context

    @property
    def conn(self) -> EdgeDBAnyConn:
        return self.db_context.get()

    async def count_by_path_pattern(self, ns_path: StrOrPath, pattern: str) -> int:
        query = """
            SELECT count(
                File
                FILTER
                    re_test(str_lower(<str>$pattern), str_lower(.path))
                    AND
                    .namespace.path = <str>$ns_path
            )
        """
        return cast(
            int,
            await self.conn.query_required_single(
                query, ns_path=str(ns_path), pattern=pattern
            )
        )

    async def _create_missing_mediatypes(self, names: Iterable[str]) -> None:
        """
        Create all mediatypes that do not exist in the database.

        Args:
            names (Iterable[str]): Media types names to create.
        """
        query = """
            WITH
                mediatypes := {DISTINCT array_unpack(<array<str>>$names)},
                missing := (
                    SELECT
                        mediatypes
                    FILTER
                        mediatypes NOT IN (SELECT MediaType { name }).name
                )
            FOR name in {missing}
            UNION (
                INSERT MediaType {
                    name := name
                }
            )
        """

        await self.conn.query(query, names=list(names))

    async def delete(self, ns_path: StrOrPath, path: StrOrPath) -> File:
        query = """
            SELECT (
                DELETE
                    File
                FILTER
                    str_lower(.path) = str_lower(<str>$path)
                    AND
                    .namespace.path = <str>$ns_path
                LIMIT 1
            ) { id, name, path, size, mtime, mediatype: { name } }
        """

        try:
            obj = await self.conn.query_required_single(
                query, ns_path=str(ns_path), path=str(path)
            )
        except edgedb.NoDataError as exc:
            raise errors.FileNotFound() from exc

        return _from_db(str(ns_path), obj)

    async def delete_all_with_prefix(
        self, ns_path: StrOrPath, prefix: StrOrPath
    ) -> None:
        query = """
            DELETE
                File
            FILTER
                .path ILIKE <str>$prefix ++ '%'
                AND
                .namespace.path = <str>$ns_path
        """

        await self.conn.query(query, ns_path=str(ns_path), prefix=str(prefix))

    async def exists_at_path(self, ns_path: StrOrPath, path: StrOrPath) -> bool:
        query = """
            SELECT EXISTS (
                SELECT
                    File
                FILTER
                    str_lower(.path) = str_lower(<str>$path)
                    AND
                    .namespace.path = <str>$ns_path
            )
        """

        exists = await self.conn.query_required_single(
            query, ns_path=str(ns_path), path=str(path)
        )
        return cast(bool, exists)

    async def exists_with_id(self, ns_path: StrOrPath, file_id: StrOrUUID) -> bool:
        query = """
            SELECT EXISTS (
                SELECT
                    File
                FILTER
                    .id = <uuid>$file_id
                    AND
                    .namespace.path = <str>$ns_path
            )
        """

        exists = await self.conn.query_required_single(
            query, ns_path=str(ns_path), file_id=file_id
        )
        return cast(bool, exists)

    async def get_by_id_batch(
        self, ns_path: StrOrPath, ids: Iterable[StrOrUUID]
    ) -> list[File]:
        query = """
            SELECT
                File {
                    id, name, path, size, mtime, mediatype: { name },
                }
            FILTER
                .id IN {array_unpack(<array<uuid>>$ids)}
                AND
                .namespace.path = <str>$namespace
            ORDER BY
                str_lower(.path) ASC
        """
        objs = await self.conn.query(
            query, namespace=str(ns_path), ids=list(ids),
        )

        return [_from_db(str(ns_path), obj) for obj in objs]

    async def get_by_path(self, ns_path: StrOrPath, path: StrOrPath) -> File:
        query = """
            SELECT
                File {
                    id, name, path, size, mtime, mediatype: { name }
                }
            FILTER
                str_lower(.path) = str_lower(<str>$path)
                AND
                .namespace.path = <str>$ns_path
            LIMIT 1
        """
        try:
            obj = await self.conn.query_required_single(
                query, ns_path=str(ns_path), path=str(path)
            )
        except edgedb.NoDataError as exc:
            raise errors.FileNotFound() from exc

        return _from_db(str(ns_path), obj)

    async def get_by_path_batch(
        self, ns_path: StrOrPath, paths: Iterable[StrOrPath],
    ) -> list[File]:
        query = """
            SELECT
                File {
                    id, name, path, size, mtime, mediatype: { name },
                }
            FILTER
                str_lower(.path) IN {array_unpack(<array<str>>$paths)}
                AND
                .namespace.path = <str>$ns_path
            ORDER BY
                str_lower(.path) ASC
        """
        ns_path = str(ns_path)
        objs = await self.conn.query(
            query,
            ns_path=ns_path,
            paths=[str(p).lower() for p in paths]
        )
        return [_from_db(ns_path, obj) for obj in objs]

    async def incr_size_batch(
        self, ns_path: StrOrPath, paths: Iterable[StrOrPath], value: int
    ) -> None:
        if not value:
            return

        query = """
            UPDATE
                File
            FILTER
                str_lower(.path) IN array_unpack(<array<str>>$paths)
                AND
                .namespace.path = <str>$ns_path
            SET {
                size := .size + <int64>$size
            }
        """
        await self.conn.query(
            query,
            ns_path=str(ns_path),
            paths=[str(p).lower() for p in paths],
            size=value,
        )

    async def replace_path_prefix(
        self, ns_path: StrOrPath, prefix: StrOrPath, next_prefix: StrOrPath
    ) -> None:
        query = """
            UPDATE
                File
            FILTER
                str_lower(.path) LIKE str_lower(<str>$prefix) ++ '/%'
                AND
                .namespace.path = <str>$ns_path
            SET {
                path := re_replace(
                    str_lower(<str>$prefix), <str>$next_prefix, str_lower(.path)
                )
            }
        """
        await self.conn.query(
            query,
            ns_path=str(ns_path),
            prefix=str(prefix),
            next_prefix=str(next_prefix),
        )

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
            "namespace": file.ns_path,
        }

        try:
            obj = await self.conn.query_required_single(query, **params)
        except edgedb.ConstraintViolationError as exc:
            raise errors.FileAlreadyExists() from exc

        return _from_db(file.ns_path, obj)

    async def save_batch(self, files: Iterable[File]) -> None:
        query = """
            WITH
                files := array_unpack(<array<json>>$files),
            FOR file IN {files}
            UNION (
                INSERT File {
                    name := <str>file['name'],
                    path := <str>file['path'],
                    size := <int64>file['size'],
                    mtime := <float64>file['mtime'],
                    mediatype := (
                        SELECT
                            MediaType
                        FILTER
                            .name = <str>file['mediatype']
                    ),
                    namespace := (
                        SELECT
                            Namespace
                        FILTER
                            .path = <str>file['ns_path']
                        LIMIT 1
                    ),
                }
                UNLESS CONFLICT
            )
        """

        files = list(files)
        data = [file.json(exclude={"id"}) for file in files]
        if not data:
            return

        mediatypes = [file.mediatype for file in files]
        await self._create_missing_mediatypes(mediatypes)
        await self.conn.query(query, files=data)

    async def update(self, file_update: FileUpdate) -> File:
        hints = get_type_hints(FileUpdate)
        statements = [
            f"{key} := {autocast.autocast(hints[key])}${key}"
            for key in file_update if key != "id"
        ]
        query = f"""
            SELECT (
                UPDATE
                    File
                FILTER
                    .id = <uuid>$id
                SET {{
                    {','.join(statements)}
                }}
            ) {{
                id, name, path, size, mtime,
                mediatype: {{ name }},
                namespace: {{ path }}
            }}
            LIMIT 1
        """
        obj = await self.conn.query_required_single(query, **file_update)
        return _from_db(obj.namespace.path, obj)
