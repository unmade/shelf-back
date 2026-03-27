from __future__ import annotations

import re
from typing import TYPE_CHECKING

from tortoise.exceptions import DoesNotExist, IntegrityError
from tortoise.expressions import F, Q
from tortoise.functions import Lower

from app.app.files.domain import File, MountedFile
from app.app.files.domain.mount import MountPoint
from app.app.files.domain.path import Path
from app.app.files.repositories import IFileRepository
from app.app.files.repositories.file import FileUpdate
from app.infrastructure.database.tortoise import models
from app.toolkit.mediatypes import MediaType

from .file_member import ActionFlag

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence
    from uuid import UUID

    from app.app.files.domain import AnyFile, AnyPath
    from app.typedefs import StrOrUUID

__all__ = ["FileRepository"]


def _from_db(ns_path: str | None, obj: models.File) -> File:
    return File(
        id=obj.id,
        ns_path=ns_path or obj.namespace.path,
        name=obj.name,
        path=Path(obj.path),
        chash=obj.chash,
        size=obj.size,
        modified_at=obj.modified_at,
        mediatype=obj.mediatype.name,
    )


def _from_db_v2(ns_path: str, obj: models.File) -> AnyFile:
    mount_point_obj = getattr(obj, "_mount_point", None)
    if mount_point_obj is None:
        return File(
            id=obj.id,
            ns_path=ns_path,
            name=obj.name,
            path=Path(obj.path),
            chash=obj.chash,
            size=obj.size,
            modified_at=obj.modified_at,
            shared=getattr(obj, "_shared", False),
            mediatype=obj.mediatype.name,
        )

    mount_point = MountPoint(
        display_name=mount_point_obj.display_name,
        source=MountPoint.Source(
            ns_path=obj.namespace.path,
            path=Path(obj.path),
        ),
        folder=MountPoint.ContainingFolder(
            ns_path=ns_path,
            path=Path(mount_point_obj.parent.path),
        ),
        actions=ActionFlag.load(mount_point_obj.member.actions),
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
                .filter(
                    namespace__path=str(ns_path),
                    path__iexact=str(path),
                )
                .select_related("mediatype")
                .get()
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

    async def get_by_chash_batch(
        self, chashes: Sequence[str]
    ) -> list[File]:
        objs = await (
            models.File
            .filter(chash__in=chashes)
            .select_related("mediatype", "namespace")
        )
        return [_from_db(None, obj) for obj in objs]

    async def get_by_id(self, file_id: UUID) -> File:
        try:
            obj = await (
                models.File
                .filter(id=file_id)
                .select_related("mediatype", "namespace")
                .get()
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
            .select_related("mediatype", "namespace")
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
                .filter(
                    namespace__path=str(ns_path),
                    path__iexact=str(path),
                )
                .select_related("mediatype")
                .get()
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
                path__in=[str(p) for p in paths],
            )
            .select_related("mediatype")
            .order_by("path")
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

    async def list_files(
        self,
        ns_path: AnyPath,
        *,
        included_mediatypes: Sequence[str] | None = None,
        excluded_mediatypes: Sequence[str] | None = None,
        offset: int,
        limit: int = 25,
    ) -> list[File]:
        qs = models.File.filter(namespace__path=str(ns_path))
        if included_mediatypes:
            qs = qs.filter(mediatype__name__in=included_mediatypes)
        if excluded_mediatypes:
            qs = qs.filter(mediatype__name__not_in=excluded_mediatypes)

        objs = await (
            qs
            .select_related("mediatype")
            .order_by("path")
            .offset(offset)
            .limit(limit)
        )
        return [_from_db(str(ns_path), obj) for obj in objs]

    async def list_with_prefix(
        self, ns_path: AnyPath, prefix: AnyPath
    ) -> list[AnyFile]:
        # That method is poor design of shared files. it was possible to do it
        # in gel within a single query. For now let's keep it as is until shared files
        # implementation is reconsidered.
        prefix_str = str(prefix)
        parent_path = str(Path(prefix_str)) if prefix_str else ""

        pattern = f"^{re.escape(prefix_str)}[^/]+$"
        direct_children = await (
            models.File
            .filter(
                namespace__path=str(ns_path),
                path__iposix_regex=pattern,
            )
            .select_related("mediatype", "namespace")
        )

        # Get mount points for the parent folder
        mounted_files: list[models.File] = []
        if parent_path:
            mount_points = await (
                models.FileMemberMountPoint
                .filter(
                    parent__path=parent_path,
                    parent__namespace__path=str(ns_path),
                )
                .select_related(
                    "member__file__mediatype",
                    "member__file__namespace",
                    "member",
                    "parent",
                )
            )
            for mp in mount_points:
                file_obj = mp.member.file
                file_obj._mount_point = mp
                file_obj._shared = True
                mounted_files.append(file_obj)

        # Also check for shared status on direct children
        direct_file_ids = [obj.id for obj in direct_children]
        shared_ids: set[UUID] = set()
        if direct_file_ids:
            shared_members = await (
                models.FileMember
                .filter(file_id__in=direct_file_ids)
                .values_list("file_id", flat=True)
            )
            shared_ids = {UUID(str(mid)) for mid in shared_members}

        for obj in direct_children:
            obj._shared = obj.id in shared_ids
            obj._mount_point = None

        all_files = direct_children + mounted_files
        results = [_from_db_v2(str(ns_path), obj) for obj in all_files]

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
            .select_related("mediatype", "namespace")
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
            # Replace only the first occurrence of the prefix
            new_path = str(obj.path).replace(
                str(at_prefix), str(to_prefix), 1
            )
            obj.path = new_path
            obj.name = Path(new_path).name
            if to_ns is not None:
                obj.namespace = to_ns
            await obj.save(update_fields=["path", "name", "namespace_id"])

    async def save(self, file: File) -> File:
        mediatype, _ = await models.MediaType.get_or_create(
            name=file.mediatype,
        )
        namespace = await models.Namespace.get(path=file.ns_path)
        try:
            obj = await models.File.create(
                name=file.name,
                path=str(file.path),
                chash=str(file.chash),
                size=file.size,
                modified_at=file.modified_at,
                mediatype=mediatype,
                namespace=namespace,
            )
        except IntegrityError as exc:
            raise File.AlreadyExists() from exc
        return _from_db(file.ns_path, obj)

    async def save_batch(self, files: Iterable[File]) -> None:
        files = list(files)
        if not files:
            return

        mediatypes_names = {f.mediatype for f in files}
        for name in mediatypes_names:
            await models.MediaType.get_or_create(name=name)

        ns_paths = {f.ns_path for f in files}
        namespaces = {
            ns.path: ns
            for ns in await models.Namespace.filter(path__in=ns_paths)
        }
        mediatypes = {
            mt.name: mt
            for mt in await models.MediaType.filter(
                name__in=mediatypes_names
            )
        }

        objs = [
            models.File(
                name=f.name,
                path=str(f.path),
                chash=str(f.chash),
                size=f.size,
                modified_at=f.modified_at,
                mediatype=mediatypes[f.mediatype],
                namespace=namespaces[f.ns_path],
            )
            for f in files
        ]
        await models.File.bulk_create(objs, ignore_conflicts=True)

    async def set_chash_batch(
        self, items: Iterable[tuple[UUID, str]]
    ) -> None:
        for file_id, new_chash in items:
            await (
                models.File
                .filter(id=file_id)
                .update(chash=new_chash)
            )

    async def update(self, file: File, fields: FileUpdate) -> File:
        update_kwargs: dict[str, object] = {}
        ns_path = fields.pop("ns_path", None)
        if ns_path is not None:
            namespace = await models.Namespace.get(path=ns_path)
            update_kwargs["namespace"] = namespace

        for key, value in fields.items():
            update_kwargs[key] = str(value) if key == "path" else value

        await (
            models.File.filter(id=file.id).update(**update_kwargs)
        )

        try:
            obj = await (
                models.File
                .filter(id=file.id)
                .select_related("mediatype", "namespace")
                .get()
            )
        except DoesNotExist as exc:
            raise File.NotFound() from exc

        return _from_db(obj.namespace.path, obj)
