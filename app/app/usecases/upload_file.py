from __future__ import annotations

from typing import IO, TYPE_CHECKING

from app import errors

if TYPE_CHECKING:
    from app.app.services import NamespaceService, UserService
    from app.domain.entities import File
    from app.typedefs import StrOrPath

__all__ = ["UploadFile"]


class UploadFile:
    def __init__(self, namespace_service: NamespaceService, user_service: UserService):
        self.namespace_service = namespace_service
        self.user_service = user_service

    async def __call__(
        self, ns_path: StrOrPath, path: StrOrPath, content: IO[bytes],
    ) -> File:
        ns = await self.namespace_service.get_by_path(str(ns_path))
        account = await self.user_service.get_account(ns.owner_id)
        if account.storage_quota is not None:
            size = content.seek(0, 2)
            used = await self.namespace_service.get_space_used_by_owner_id(ns.owner_id)
            if (used + size) > account.storage_quota:
                raise errors.StorageQuotaExceeded()

        return await self.namespace_service.add_file(ns_path, path, content)
