from __future__ import annotations

import textwrap
from typing import (
    TYPE_CHECKING,
    Iterable,
    Sequence,
    cast,
    get_type_hints,
)
from uuid import UUID

import gel

from app.app.files.domain import File, MountedFile
from app.app.files.domain.mount import MountPoint
from app.app.files.domain.path import Path
from app.app.files.repositories import IFileRepository
from app.app.files.repositories.file import FileUpdate
from app.infrastructure.database.edgedb import autocast
from app.toolkit import json_

from .file_member import ActionFlag

if TYPE_CHECKING:
    from collections.abc import Mapping

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
        chash=obj.chash,
        size=obj.size,
        modified_at=obj.modified_at,
        mediatype=obj.mediatype.name,
    )


def _from_db_v2(ns_path: str, obj) -> AnyFile:
    if not getattr(obj, "mount_point", None):
        return File(
            id=obj.id,
            ns_path=ns_path,
            name=obj.name,
            path=obj.path,
            chash=obj.chash,
            size=obj.size,
            modified_at=obj.modified_at,
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
        actions=ActionFlag.load(obj.mount_point.member.actions),
    )

    return MountedFile(
        id=obj.id,
        ns_path=mount_point.folder.ns_path,
        name=mount_point.display_path.name,
        path=mount_point.display_path,
        chash=obj.chash,
        size=obj.size,
        modified_at=obj.modified_at,
        mediatype=obj.mediatype.name,
        shared=True,
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
        """Create all mediatypes that do not exist in the database."""
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
            ) { id, name, path, chash, size, modified_at, mediatype: { name } }
        """

        try:
            obj = await self.conn.query_required_single(
                query, ns_path=str(ns_path), path=str(path)
            )
        except gel.NoDataError as exc:
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

    async def delete_all_with_prefix_batch(
        self, items: Mapping[str, Sequence[AnyPath]]
    ) -> None:
        if not items:
            return

        filter_clause = " OR ".join(
            [
                textwrap.dedent(
                    f"""\
                    (
                        .path ILIKE (
                            FOR prefix in {{array_unpack(<array<str>>$prefixes_{i})}}
                            UNION (
                                SELECT prefix ++ '%'
                            )
                        )
                        AND .namespace.path = <str>$ns_path_{i}
                    )
                    """
                )
                for i in range(len(items))
            ]
        )

        kwargs: dict[str, str | list[str]] = {}
        for i, (ns_path, prefixes) in enumerate(items.items()):
            kwargs[f"ns_path_{i}"] = ns_path
            kwargs[f"prefixes_{i}"] = [str(prefix) for prefix in prefixes]

        query = f"""
            DELETE
                File {{
                    id, name, path, chash, size, modified_at,
                    mediatype: {{ name }},
                    namespace: {{ path }}
                }}
            FILTER
                {filter_clause}
        """
        await self.conn.query(query, **kwargs)

    async def delete_batch(
        self, ns_path: AnyPath, paths: Sequence[AnyPath]
    ) -> list[File]:
        query = """
            SELECT (
                DELETE
                    File
                FILTER
                    str_lower(.path) IN {array_unpack(<array<str>>$paths)}
                    AND
                    .namespace.path = <str>$ns_path
            ) { id, name, path, chash, size, modified_at, mediatype: { name } }
        """

        objs = await self.conn.query(
            query,
            ns_path=str(ns_path),
            paths=[str(path).lower() for path in paths],
        )
        return [_from_db(str(ns_path), obj) for obj in objs]

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

    async def exists_with_id(self, ns_path: AnyPath, file_id: UUID) -> bool:
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

    async def get_by_chash_batch(self, chashes: Sequence[str]) -> list[File]:
        query = """
            SELECT
                File {
                    id, name, path, chash, size, modified_at, mediatype: { name },
                    namespace: { path }
                }
            FILTER
                .chash IN {array_unpack(<array<str>>$chashes)}
        """

        objs = await self.conn.query(query, chashes=chashes)
        return [_from_db(None, obj) for obj in objs]

    async def get_by_id(self, file_id: UUID) -> File:
        query = """
            SELECT
                File {
                    id, name, path, chash, size, modified_at, mediatype: { name },
                    namespace: { path }
                }
            FILTER
                .id = <uuid>$file_id
        """
        try:
            obj = await self.conn.query_required_single(query, file_id=file_id)
        except gel.NoDataError as exc:
            raise File.NotFound() from exc
        return _from_db(obj.namespace.path, obj)

    async def get_by_id_batch(self, ids: Iterable[StrOrUUID]) -> list[File]:
        query = """
            SELECT
                File {
                    id,
                    name,
                    path,
                    chash,
                    size,
                    modified_at,
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
                    id, name, path, chash, size, modified_at, mediatype: { name }
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
        except gel.NoDataError as exc:
            raise File.NotFound() from exc

        return _from_db(str(ns_path), obj)

    async def get_by_path_batch(
        self, ns_path: AnyPath, paths: Iterable[AnyPath],
    ) -> list[File]:
        query = """
            SELECT
                File {
                    id, name, path, chash, size, modified_at, mediatype: { name },
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

    async def incr_size(
        self, ns_path: AnyPath, items: Sequence[tuple[AnyPath, int]]
    ) -> None:
        query = """
            WITH
                entries := array_unpack(<array<json>>$entries),
                namespace := (
                    SELECT
                        Namespace
                    FILTER
                        .path = <str>$ns_path
                )
            FOR entry IN {entries}
            UNION (
                UPDATE File
                FILTER
                    str_lower(.path) = <str>entry['path']
                    AND
                    .namespace = namespace
                SET {
                    size := .size + <int64>entry['size']
                }
            )
        """

        await self.conn.query(
            query,
            ns_path=ns_path,
            entries=[
                json_.dumps({
                    "path": str(path),
                    "size": size,
                })
                for path, size in items
                if size
            ],
        )

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

    async def list_files(
        self,
        ns_path: AnyPath,
        *,
        included_mediatypes: Sequence[str] | None = None,
        excluded_mediatypes: Sequence[str] | None = None,
        offset: int,
        limit: int = 25,
    ) -> list[File]:
        """Lists all files in the given namespace."""
        kwargs = {
            "namespace": str(ns_path),
            "offset": offset,
            "limit": limit,
        }

        filter_clauses = [".namespace.path = <str>$namespace"]
        if included_mediatypes:
            filter_clauses.append(
                ".mediatype.name IN {array_unpack(<array<str>>$included_types)}"
            )
            kwargs["included_types"] = included_mediatypes

        if excluded_mediatypes:
            filter_clauses.append(
                ".mediatype.name NOT IN {array_unpack(<array<str>>$excluded_types)}"
            )
            kwargs["excluded_types"] = excluded_mediatypes

        query = f"""
            SELECT
                File {{
                    id, name, path, chash, size, modified_at, mediatype: {{ name }},
                }}
            FILTER
                {" AND ".join(filter_clauses)}
            ORDER BY
                .path
            OFFSET
                <int64>$offset
            LIMIT
                <int64>$limit
        """

        files = await self.conn.query(query, **kwargs)
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
                    chash,
                    size,
                    modified_at,
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
                                member: { actions },
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

    async def list_all_with_prefix_batch(
        self, items:Mapping[str, Sequence[AnyPath]]
    ) -> list[File]:
        if not items:
            return []

        filter_clause = " OR ".join(
            [
                textwrap.dedent(
                    f"""\
                    (
                        .path ILIKE (
                            FOR prefix in {{array_unpack(<array<str>>$prefixes_{i})}}
                            UNION (
                                SELECT prefix ++ '%'
                            )
                        )
                        AND .namespace.path = <str>$ns_path_{i}
                    )
                    """
                )
                for i in range(len(items))
            ]
        )

        kwargs: dict[str, str | list[str]] = {}
        for i, (ns_path, prefixes) in enumerate(items.items()):
            kwargs[f"ns_path_{i}"] = ns_path
            kwargs[f"prefixes_{i}"] = [str(prefix) for prefix in prefixes]

        query = f"""
            SELECT
                File {{
                    id, name, path, chash, size, modified_at,
                    mediatype: {{ name }},
                    namespace: {{ path }}
                }}
            FILTER
                {filter_clause}
        """

        objs = await self.conn.query(query, **kwargs)
        return [_from_db(None, obj) for obj in objs]

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
                    <str>$at_prefix, <str>$to_prefix, .path
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
                    chash := <str>$chash,
                    size := <int64>$size,
                    modified_at := <datetime>$modified_at,
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
            ) { id, name, path, chash, size, modified_at, mediatype: { name } }
        """

        params = {
            "name": file.name,
            "path": str(file.path),
            "chash": str(file.chash),
            "size": file.size,
            "modified_at": file.modified_at,
            "mediatype": file.mediatype,
            "namespace": file.ns_path,
        }

        try:
            obj = await self.conn.query_required_single(query, **params)
        except gel.ConstraintViolationError as exc:
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
                    chash := <str>file['chash'],
                    size := <int64>file['size'],
                    modified_at := <datetime>file['modified_at'],
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
        data = [file.model_dump_json() for file in files]
        if not data:
            return

        mediatypes = [file.mediatype for file in files]
        await self._create_missing_mediatypes(mediatypes)
        await self.conn.query(query, files=data)

    async def set_chash_batch(self, items: Iterable[tuple[UUID, str]]) -> None:
        query = """
            WITH
                entries := array_unpack(<array<json>>$entries),
            FOR entry IN {entries}
            UNION (
                UPDATE File
                FILTER
                    .id = <uuid>entry['file_id']
                SET {
                    chash := <str>entry['chash'],
                }
            )
        """

        await self.conn.query(
            query,
            entries=[
                json_.dumps({
                    "file_id": str(file_id),
                    "chash": chash,
                })
                for file_id, chash in items
            ],
        )

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
                id, name, path, chash, size, modified_at,
                mediatype: {{ name }},
                namespace: {{ path }}
            }}
            LIMIT 1
        """
        obj = await self.conn.query_required_single(
            query, file_id=file.id, ns_path=ns_path, **fields
        )
        return _from_db(obj.namespace.path, obj)
