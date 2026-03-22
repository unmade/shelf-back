from __future__ import annotations

from typing import TYPE_CHECKING

from tortoise.exceptions import DoesNotExist

from app.app.files.domain import Namespace
from app.app.files.repositories import INamespaceRepository
from app.infrastructure.database.tortoise import models

if TYPE_CHECKING:
    from app.app.files.domain import AnyPath
    from app.typedefs import StrOrUUID

__all__ = ["NamespaceRepository"]


class NamespaceRepository(INamespaceRepository):
    async def get_by_owner_id(self, owner_id: StrOrUUID) -> Namespace:
        try:
            obj = await models.Namespace.get(owner_id=owner_id)
        except DoesNotExist as exc:
            msg = f"Namespace with owner_id={owner_id} does not exist"
            raise Namespace.NotFound(msg) from exc
        return Namespace(
            id=obj.id,
            path=obj.path,
            owner_id=obj.owner_id  # type: ignore[attr-defined]
        )

    async def get_by_path(self, path: AnyPath) -> Namespace:
        try:
            obj = await models.Namespace.get(path=str(path))
        except DoesNotExist as exc:
            msg = f"Namespace with path={path} does not exist"
            raise Namespace.NotFound(msg) from exc
        return Namespace(
            id=obj.id,
            path=obj.path,
            owner_id=obj.owner_id  # type: ignore[attr-defined]
        )

    async def get_space_used_by_owner_id(self, owner_id: StrOrUUID) -> int:
        sizes: list[int] = await (  # type: ignore[assignment]
            models.File.filter(
                namespace__owner_id=owner_id,
                path=".",
            )
            .values_list("size", flat=True)
        )
        return sum(sizes)

    async def save(self, namespace: Namespace) -> Namespace:
        obj = models.Namespace(
            path=str(namespace.path),
            owner_id=namespace.owner_id,
        )
        await obj.save()
        return namespace.model_copy(update={"id": obj.id})
