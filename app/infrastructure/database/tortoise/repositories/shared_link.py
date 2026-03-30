from __future__ import annotations

from typing import TYPE_CHECKING

from tortoise.exceptions import DoesNotExist, IntegrityError

from app.app.files.domain import File, SharedLink
from app.app.files.repositories import ISharedLinkRepository
from app.infrastructure.database.tortoise import models

if TYPE_CHECKING:
    from uuid import UUID

__all__ = ["SharedLinkRepository"]


def _from_db(obj: models.SharedLink) -> SharedLink:
    return SharedLink(
        id=obj.id,
        file_id=obj.file_id,  # type: ignore[attr-defined]
        token=obj.token,
        created_at=obj.created_at,
    )


class SharedLinkRepository(ISharedLinkRepository):
    async def delete(self, token: str) -> None:
        await models.SharedLink.filter(token=token).delete()

    async def get_by_file_id(self, file_id: UUID) -> SharedLink:
        try:
            obj = await models.SharedLink.get(file_id=file_id)
        except DoesNotExist as exc:
            raise SharedLink.NotFound from exc
        return _from_db(obj)

    async def get_by_token(self, token: str) -> SharedLink:
        try:
            obj = await models.SharedLink.get(token=token)
        except DoesNotExist as exc:
            raise SharedLink.NotFound from exc
        return _from_db(obj)

    async def list_by_ns(
        self, ns_path: str, *, offset: int = 0, limit: int = 25
    ) -> list[SharedLink]:
        objs = await (
            models.SharedLink
            .filter(file__namespace__path=ns_path)
            .order_by("-created_at")
            .offset(offset)
            .limit(limit)
        )
        return [_from_db(obj) for obj in objs]

    async def save(self, shared_link: SharedLink) -> SharedLink:
        try:
            obj = await models.SharedLink.get(file_id=shared_link.file_id)
            return _from_db(obj)
        except DoesNotExist:
            pass

        try:
            obj = await models.SharedLink.create(
                token=shared_link.token,
                file_id=shared_link.file_id,
                created_at=shared_link.created_at,
            )
        except IntegrityError as exc:
            raise File.NotFound() from exc

        return shared_link.model_copy(update={"id": obj.id})
