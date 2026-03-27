from __future__ import annotations

import re
from typing import TYPE_CHECKING

from app.app.files.domain import MountPoint, Path
from app.app.files.repositories.mount import IMountRepository, MountPointUpdate
from app.infrastructure.database.tortoise import models

from .file_member import ActionFlag

if TYPE_CHECKING:
    from app.app.files.domain import AnyPath

__all__ = ["MountRepository"]


def _from_db(ns_path: str | AnyPath, obj: models.FileMemberMountPoint) -> MountPoint:
    member = obj.member
    file = member.file
    namespace = file.namespace
    return MountPoint(
        display_name=obj.display_name,
        actions=ActionFlag.load(member.actions),
        source=MountPoint.Source(
            ns_path=namespace.path,
            path=Path(file.path),
        ),
        folder=MountPoint.ContainingFolder(
            ns_path=str(ns_path),
            path=Path(obj.parent.path),
        ),
    )


class MountRepository(IMountRepository):
    async def count_by_name_pattern(
        self, ns_path: AnyPath, path: AnyPath, pattern: str
    ) -> int:
        objs = await (
            models.FileMemberMountPoint
            .filter(
                parent__path=str(path),
                parent__namespace__path=str(ns_path),
            )
        )
        compiled = re.compile(pattern, re.IGNORECASE)
        return sum(1 for obj in objs if compiled.search(obj.display_name))

    async def get_closest_by_source(
        self,
        source_ns_path: AnyPath,
        source_path: AnyPath,
        target_ns_path: AnyPath,
    ) -> MountPoint:
        path = Path(source_path)
        parents = list(path.parents)
        paths = [str(path)] + [str(p) for p in parents if p != "."]

        objs = await (
            models.FileMemberMountPoint
            .filter(
                member__file__namespace__path=str(source_ns_path),
                member__file__path__in=paths,
                parent__namespace__path=str(target_ns_path),
            )
            .select_related("member__file__namespace", "parent")
            .order_by("-member__file__path")
            .limit(1)
        )
        if not objs:
            raise MountPoint.NotFound()

        return _from_db(target_ns_path, objs[0])

    async def get_closest(self, ns_path: AnyPath, path: AnyPath) -> MountPoint:
        path = Path(path)
        parents = list(path.parents)

        parent_paths = [str(p) for p in parents]
        names = [path.name] + [p.name for p in parents if p != "."]

        objs = await (
            models.FileMemberMountPoint
            .filter(
                parent__path__in=parent_paths,
                parent__namespace__path=str(ns_path),
                display_name__in=names,
            )
            .select_related("member__file__namespace", "parent")
            .order_by("-parent__path")
            .limit(1)
        )
        if not objs:
            raise MountPoint.NotFound()

        mount_point = _from_db(ns_path, objs[0])
        if not Path(path).is_relative_to(mount_point.display_path):
            raise MountPoint.NotFound()
        return mount_point

    async def list_all(self, ns_path: AnyPath) -> list[MountPoint]:
        objs = await (
            models.FileMemberMountPoint
            .filter(parent__namespace__path=str(ns_path))
            .select_related("member__file__namespace", "parent")
        )
        return [_from_db(ns_path, obj) for obj in objs]

    async def save(self, entity: MountPoint) -> MountPoint:
        namespace = await models.Namespace.get(path=str(entity.folder.ns_path))
        member = await (
            models.FileMember
            .filter(
                file__namespace__path=str(entity.source.ns_path),
                file__path=str(entity.source.path),
                user_id=namespace.owner_id,  # type: ignore[attr-defined]
            )
            .get()
        )
        parent = await models.File.get(
            namespace__path=str(entity.folder.ns_path),
            path=str(entity.folder.path),
        )
        await models.FileMemberMountPoint.create(
            display_name=entity.display_name,
            member=member,
            parent=parent,
        )
        return entity

    async def update(
        self, mount_point: MountPoint, fields: MountPointUpdate
    ) -> MountPoint:
        obj = await (
            models.FileMemberMountPoint
            .filter(
                parent__namespace__path=str(mount_point.folder.ns_path),
                parent__path=str(mount_point.folder.path),
                display_name=mount_point.display_name,
            )
            .select_related("member__file__namespace", "parent")
            .get()
        )

        next_parent = await models.File.get(
            namespace__path=str(mount_point.folder.ns_path),
            path=str(fields["folder"]),
        )

        obj.parent = next_parent
        obj.display_name = fields["display_name"]
        await obj.save(update_fields=["parent_id", "display_name"])

        # Re-fetch to get updated relations
        obj = await (
            models.FileMemberMountPoint
            .filter(id=obj.id)
            .select_related("member__file__namespace", "parent")
            .get()
        )
        return _from_db(mount_point.folder.ns_path, obj)
