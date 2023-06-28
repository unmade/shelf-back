from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Iterable,
    Sequence,
    cast,
    get_type_hints,
)

import edgedb

from app.app.files.domain import File, MountedFile
from app.app.files.domain.mount import MountPoint
from app.app.files.domain.path import Path
from app.app.files.repositories import IFileRepository
from app.app.files.repositories.file import FileUpdate
from app.infrastructure.database.edgedb import autocast

if TYPE_CHECKING:
    from app.app.files.domain import AnyFile, AnyPath
    from app.infrastructure.database.edgedb.typedefs import EdgeDBAnyConn, EdgeDBContext
    from app.typedefs import StrOrUUID

__all__ = ["FileRepository"]


def _from_db(ns_path: str | None, obj) -> File:
    return File(
        id=obj.id,
        ns_path=ns_path or obj.namespace.path,
        name=obj.name,
        path=obj.path,
        size=obj.size,
        mtime=obj.mtime,
        mediatype=obj.mediatype.name,
    )


def _from_db_v2(ns_path: str, obj) -> AnyFile:
    if not getattr(obj, "mount_point", None):
        return File(
            id=obj.id,
            ns_path=ns_path,
            name=obj.name,
            path=obj.path,
            size=obj.size,
            mtime=obj.mtime,
            shared=obj.shared,
            mediatype=obj.mediatype.name,
        )

    mount_point = MountPoint(
        display_name=obj.mount_point.display_name,
        source=MountPoint.Source(
            ns_path=obj.namespace.path,
            path=obj.path,
        ),
        folder=MountPoint.ContainingFolder(
            ns_path=ns_path,
            path=obj.mount_point.parent.path
        ),
    )

    return MountedFile(
        id=obj.id,
        ns_path=mount_point.folder.ns_path,
        name=mount_point.display_path.name,
        path=mount_point.display_path,
        size=obj.size,
        mtime=obj.mtime,
        mediatype=obj.mediatype.name,
        mount_point=mount_point,
    )


class FileRepository(IFileRepository):
    def __init__(self, db_context: EdgeDBContext):
        self.db_context = db_context

    @property
    def conn(self) -> EdgeDBAnyConn:
        return self.db_context.get()

    async def count_by_path_pattern(self, ns_path: AnyPath, pattern: str) -> int:
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

    async def delete(self, ns_path: AnyPath, path: AnyPath) -> File:
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
            raise File.NotFound() from exc

        return _from_db(str(ns_path), obj)

    async def delete_all_with_prefix(
        self, ns_path: AnyPath, prefix: AnyPath
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

    async def exists_at_path(self, ns_path: AnyPath, path: AnyPath) -> bool:
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

    async def exists_with_id(self, ns_path: AnyPath, file_id: StrOrUUID) -> bool:
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

    async def get_by_id(self, file_id: str) -> File:
        query = """
            SELECT
                File {
                    id, name, path, size, mtime, mediatype: { name },
                    namespace: { path }
                }
            FILTER
                .id = <uuid>$file_id
        """
        try:
            obj = await self.conn.query_required_single(query, file_id=file_id)
        except edgedb.NoDataError as exc:
            raise File.NotFound() from exc
        return _from_db(obj.namespace.path, obj)

    async def get_by_id_batch(self, ids: Iterable[StrOrUUID]) -> list[File]:
        query = """
            SELECT
                File {
                    id,
                    name,
                    path,
                    size,
                    mtime,
                    mediatype: {
                        name,
                    },
                    namespace: {
                        path,
                    },
                }
            FILTER
                .id IN {array_unpack(<array<uuid>>$ids)}
            ORDER BY
                str_lower(.path) ASC
        """
        objs = await self.conn.query(query, ids=list(ids))
        return [_from_db(None, obj) for obj in objs]

    async def get_by_path(self, ns_path: AnyPath, path: AnyPath) -> File:
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
            raise File.NotFound() from exc

        return _from_db(str(ns_path), obj)

    async def get_by_path_batch(
        self, ns_path: AnyPath, paths: Iterable[AnyPath],
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
        self, ns_path: AnyPath, paths: Iterable[AnyPath], value: int
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

    async def list_by_mediatypes(
        self,
        ns_path: AnyPath,
        mediatypes: Sequence[str],
        *,
        offset: int,
        limit: int = 25,
    ) -> list[File]:
        query = """
            SELECT
                File {
                    id, name, path, size, mtime, mediatype: { name },
                }
            FILTER
                .namespace.path = <str>$namespace
                AND
                .mediatype.name IN {array_unpack(<array<str>>$mediatypes)}
            OFFSET
                <int64>$offset
            LIMIT
                <int64>$limit
        """

        files = await self.conn.query(
            query,
            namespace=str(ns_path),
            mediatypes=mediatypes,
            offset=offset,
            limit=limit,
        )
        return [_from_db(str(ns_path), file) for file in files]

    async def list_with_prefix(
        self, ns_path: AnyPath, prefix: AnyPath
    ) -> list[AnyFile]:
        query = """
            WITH
                namespace := (SELECT Namespace FILTER .path = <str>$ns_path),
                parent := (
                    SELECT
                        File
                    FILTER
                        .path = <str>$parent_path
                        AND
                        .namespace = namespace
                    ),
                files := {
                    (
                        SELECT
                            File
                        FILTER
                            .namespace = namespace
                            AND
                            .path LIKE <str>$prefix ++ '%'
                            AND
                            .path NOT LIKE <str>$prefix ++ '%/%'
                    ),
                    (
                        SELECT
                            FileMemberMountPoint
                        FILTER
                            .parent = parent
                    ).member.file
                },
                SELECT files {
                    id,
                    name,
                    path,
                    size,
                    mtime,
                    mediatype := .mediatype { name },
                    namespace := .namespace { path },
                    shared := (
                        EXISTS (.<file[is FileMember])
                    ),
                    mount_point := (
                        SELECT
                            FileMemberMountPoint {
                                display_name,
                                parent: { path },
                            }
                        FILTER
                            .member.file.id = files.id
                            and .parent = parent
                        LIMIT 1
                    ),
                }
                ORDER BY
                    .mediatype.name = 'application/directory' DESC
                THEN
                    str_lower(.mount_point.display_name ?? .name) ASC
        """

        objs = await self.conn.query(
            query,
            ns_path=str(ns_path),
            prefix=str(prefix),
            parent_path=str(Path(prefix)),
        )
        return [_from_db_v2(str(ns_path), obj) for obj in objs]

    async def replace_path_prefix(
        self, at: tuple[AnyPath, AnyPath], to: tuple[AnyPath, AnyPath]
    ) -> None:
        at_ns_path, at_prefix = at
        to_ns_path, to_prefix = to

        query = """
            WITH
                namespace := (SELECT Namespace FILTER .path = <str>$at_ns_path),
                next_namespace := (SELECT Namespace FILTER .path = <str>$to_ns_path),
            UPDATE
                File
            FILTER
                .namespace = namespace
                AND
                .path ILIKE <str>$at_prefix ++ '/%'
            SET {
                namespace := next_namespace,
                path := re_replace(
                    str_lower(<str>$at_prefix), <str>$to_prefix, str_lower(.path)
                ),
            }
        """
        await self.conn.query(
            query,
            at_ns_path=str(at_ns_path),
            at_prefix=str(at_prefix),
            to_ns_path=str(to_ns_path),
            to_prefix=str(to_prefix),
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
            "path": str(file.path),
            "size": file.size,
            "mtime": file.mtime,
            "mediatype": file.mediatype,
            "namespace": file.ns_path,
        }

        try:
            obj = await self.conn.query_required_single(query, **params)
        except edgedb.ConstraintViolationError as exc:
            raise File.AlreadyExists() from exc

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
        data = [file.json() for file in files]
        if not data:
            return

        mediatypes = [file.mediatype for file in files]
        await self._create_missing_mediatypes(mediatypes)
        await self.conn.query(query, files=data)

    async def update(self, file: File, fields: FileUpdate) -> File:
        ns_path = fields.pop("ns_path", file.ns_path)
        hints = get_type_hints(FileUpdate)
        statements = [
            f"{key} := {autocast.autocast(hints[key])}${key}"
            for key in fields
        ]
        query = f"""
            WITH
                namespace := (SELECT Namespace FILTER .path = <str>$ns_path),
            SELECT (
                UPDATE
                    File
                FILTER
                    .id = <uuid>$file_id
                SET {{
                    namespace := namespace,
                    {','.join(statements)}
                }}
            ) {{
                id, name, path, size, mtime,
                mediatype: {{ name }},
                namespace: {{ path }}
            }}
            LIMIT 1
        """
        obj = await self.conn.query_required_single(
            query, file_id=file.id, ns_path=ns_path, **fields
        )
        return _from_db(obj.namespace.path, obj)
