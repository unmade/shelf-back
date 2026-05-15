from __future__ import annotations

import re
from typing import TYPE_CHECKING

from tortoise.exceptions import DoesNotExist, IntegrityError
from tortoise.expressions import F, Q
from tortoise.functions import Lower

from app.app.files.domain import File
from app.app.files.domain.path import Path
from app.app.files.repositories import IFileRepository
from app.app.files.repositories.file import FileUpdate
from app.infrastructure.database.tortoise import models
from app.toolkit import chash
from app.toolkit.mediatypes import MediaType

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence
    from uuid import UUID

    from app.app.files.domain import AnyPath
    from app.typedefs import StrOrUUID

__all__ = ["FileRepository"]


def _file_fields(obj: models.File) -> tuple[str, str]:
    blob_id = getattr(obj, "blob_id", None)
    if blob_id is None:
        return chash.EMPTY_CONTENT_HASH, MediaType.FOLDER

    blob = obj.blob
    assert blob is not None
    return blob.chash, blob.media_type


def _from_db(ns_path: str | None, obj: models.File) -> File:
    chash, mediatype = _file_fields(obj)
    return File(
        id=obj.id,
        blob_id=obj.blob_id,  # type: ignore[attr-defined]
        owner_id=obj.owner_id,  # type: ignore[attr-defined]
        ns_path=ns_path or obj.namespace.path,
        name=obj.name,
        path=Path(obj.path),
        chash=chash,
        size=obj.size,
        modified_at=obj.modified_at,
        mediatype=mediatype,
    )


class FileRepository(IFileRepository):
    async def count_by_path_pattern(
        self, ns_path: AnyPath, pattern: str
    ) -> int:
        return await (
            models.File
            .filter(
                namespace__path=str(ns_path),
                path__iposix_regex=pattern,
            )
            .count()
        )

    async def delete(self, ns_path: AnyPath, path: AnyPath) -> File:
        try:
            obj = await (
                models.File
                .get(
                    namespace__path=str(ns_path),
                    path__iexact=str(path),
                )
                .select_related("namespace", "blob")
            )
        except DoesNotExist as exc:
            raise File.NotFound() from exc

        file = _from_db(str(ns_path), obj)
        await obj.delete()
        return file

    async def delete_all_with_prefix(
        self, ns_path: AnyPath, prefix: AnyPath
    ) -> None:
        namespace = await models.Namespace.get(path=str(ns_path))
        await (
            models.File
            .filter(
                namespace=namespace,
                path__istartswith=str(prefix),
            )
            .delete()
        )

    async def delete_all_with_prefix_batch(
        self, items: Mapping[str, Sequence[AnyPath]]
    ) -> None:
        if not items:
            return

        namespaces = {
            ns.path: ns
            for ns in await models.Namespace.filter(
                path__in=list(items.keys())
            )
        }

        q = Q()
        for ns_path, prefixes in items.items():
            ns = namespaces[ns_path]
            for prefix in prefixes:
                q |= Q(
                    namespace=ns,
                    path__istartswith=str(prefix),
                )

        await models.File.filter(q).delete()

    async def delete_batch(
        self, ns_path: AnyPath, paths: Sequence[AnyPath]
    ) -> None:
        namespace = await models.Namespace.get(path=str(ns_path))
        await (
            models.File
            .filter(
                namespace=namespace,
                path__in=[str(p) for p in paths],
            )
            .delete()
        )

    async def exists_at_path(
        self, ns_path: AnyPath, path: AnyPath
    ) -> bool:
        return await (
            models.File
            .filter(
                namespace__path=str(ns_path),
                path__iexact=str(path),
            )
            .exists()
        )

    async def exists_with_id(
        self, ns_path: AnyPath, file_id: UUID
    ) -> bool:
        return await (
            models.File
            .filter(
                namespace__path=str(ns_path),
                id=file_id,
            )
            .exists()
        )

    async def get_by_id(self, file_id: UUID) -> File:
        try:
            obj = await (
                models.File
                .get(id=file_id)
                .select_related("blob", "namespace")
            )
        except DoesNotExist as exc:
            raise File.NotFound() from exc
        return _from_db(obj.namespace.path, obj)

    async def get_by_id_batch(
        self, ids: Iterable[StrOrUUID]
    ) -> list[File]:
        objs = await (
            models.File
            .filter(id__in=list(ids))
            .select_related("blob", "namespace")
            .annotate(lower_path=Lower("path"))
            .order_by("lower_path")
        )
        return [_from_db(None, obj) for obj in objs]

    async def get_by_path(
        self, ns_path: AnyPath, path: AnyPath
    ) -> File:
        try:
            obj = await (
                models.File
                .get(
                    namespace__path=str(ns_path),
                    path__iexact=str(path),
                )
                .select_related("blob", "namespace")
            )
        except DoesNotExist as exc:
            raise File.NotFound() from exc
        return _from_db(str(ns_path), obj)

    async def get_by_path_batch(
        self, ns_path: AnyPath, paths: Iterable[AnyPath],
    ) -> list[File]:
        objs = await (
            models.File
            .filter(
                namespace__path=str(ns_path),
            )
            .annotate(lower_path=Lower("path"))
            .filter(lower_path__in=[str(p).lower() for p in paths])
            .select_related("blob", "namespace")
            .order_by("lower_path")
        )
        return [_from_db(str(ns_path), obj) for obj in objs]

    async def incr_size_batch(
        self, ns_path: AnyPath, paths: Iterable[AnyPath], value: int
    ) -> None:
        if not value:
            return

        namespace = await models.Namespace.get(path=str(ns_path))
        await (
            models.File
            .filter(
                namespace=namespace,
                path__in=[str(p) for p in paths],
            )
            .update(size=F("size") + value)
        )

    async def list_with_prefix(self, ns_path: AnyPath, prefix: AnyPath) -> list[File]:
        prefix_str = str(prefix)
        pattern = f"^{re.escape(prefix_str)}[^/]+$"
        objs = await (
            models.File
            .filter(
                namespace__path=str(ns_path),
                path__iposix_regex=pattern,
            )
            .select_related("blob", "namespace")
        )
        results = [_from_db(str(ns_path), obj) for obj in objs]

        # Sort: folders first, then alphabetically by name (case-insensitive)
        results.sort(
            key=lambda f: (
                f.mediatype != MediaType.FOLDER,
                f.name.lower(),
            )
        )
        return results

    async def list_all_with_prefix_batch(
        self, items: Mapping[str, Sequence[AnyPath]]
    ) -> list[File]:
        if not items:
            return []

        q = Q()
        for ns_path, prefixes in items.items():
            for prefix in prefixes:
                q |= Q(
                    namespace__path=ns_path,
                    path__istartswith=str(prefix),
                )

        objs = await (
            models.File
            .filter(q)
            .select_related("blob", "namespace")
        )
        return [_from_db(None, obj) for obj in objs]

    async def replace_path_prefix(
        self, at: tuple[AnyPath, AnyPath], to: tuple[AnyPath, AnyPath]
    ) -> None:
        at_ns_path, at_prefix = at
        to_ns_path, to_prefix = to
        to_ns = None

        if str(at_ns_path) != str(to_ns_path):
            to_ns = await models.Namespace.get(path=str(to_ns_path))

        objs = await (
            models.File
            .filter(
                namespace__path=str(at_ns_path),
                path__istartswith=f"{at_prefix}/",
            )
        )
        for obj in objs:
            to_path = str(obj.path).replace(str(at_prefix), str(to_prefix), 1)
            obj.path = to_path
            obj.name = Path(to_path).name
            if to_ns is not None:
                obj.namespace = to_ns
                obj.owner_id = to_ns.owner_id  # type: ignore[attr-defined]

        await models.File.bulk_update(
            objs,
            fields=["path", "name", "namespace_id", "owner_id"],
        )

    async def save(self, file: File) -> File:
        namespace = await models.Namespace.get(path=file.ns_path)
        try:
            obj = await models.File.create(
                name=file.name,
                path=str(file.path),
                size=file.size,
                modified_at=file.modified_at,
                owner_id=namespace.owner_id,  # type: ignore[attr-defined]
                namespace=namespace,
                blob_id=file.blob_id,
            )
        except IntegrityError as exc:
            raise File.AlreadyExists() from exc
        return await self.get_by_id(obj.id)

    async def save_batch(self, files: Iterable[File]) -> None:
        files = list(files)
        if not files:
            return

        ns_paths = {f.ns_path for f in files}
        namespaces = {
            ns.path: ns
            for ns in await models.Namespace.filter(path__in=ns_paths)
        }

        objs = [
            models.File(
                name=f.name,
                path=str(f.path),
                size=f.size,
                modified_at=f.modified_at,
                owner_id=namespaces[f.ns_path].owner_id,  # type: ignore[attr-defined]
                namespace=namespaces[f.ns_path],
                blob_id=f.blob_id,
            )
            for f in files
        ]
        await models.File.bulk_create(objs, ignore_conflicts=True)

    async def update(self, file: File, fields: FileUpdate) -> File:
        update_kwargs: dict[str, object] = {}
        ns_path = fields.pop("ns_path", file.ns_path)
        if ns_path != file.ns_path:
            namespace = await models.Namespace.get(path=ns_path)
            update_kwargs["namespace"] = namespace
            update_kwargs["owner_id"] = namespace.owner_id  # type: ignore[attr-defined]

        for key, value in fields.items():
            update_kwargs[key] = str(value) if key == "path" else value

        await models.File.filter(id=file.id).update(**update_kwargs)

        obj = await (
            models.File
            .get(id=file.id)
            .select_related("blob", "namespace")
        )

        return _from_db(obj.namespace.path, obj)
