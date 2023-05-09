from __future__ import annotations

from typing import TYPE_CHECKING, cast

from app.app.files.domain import AnyFile, File
from app.app.files.services import FileCoreService, FileService, SharingService

if TYPE_CHECKING:
    from app.app.files.domain import AnyPath, SharedLink

__all__ = ["SharingUseCase"]


class SharingUseCase:
    __slots__ = ["file_service", "filecore", "sharing"]

    def __init__(
        self,
        file_service: FileService,
        filecore: FileCoreService,
        sharing: SharingService,
    ):
        self.filecore = filecore
        self.file_service = file_service
        self.sharing = sharing

    async def create_link(self, ns_path: str, path: AnyPath) -> SharedLink:
        file = await self.filecore.get_by_path(ns_path, path)
        return await self.sharing.create_link(file.id)

    async def get_link(self, ns_path: str, path: AnyPath) -> SharedLink:
        file = await self.filecore.get_by_path(ns_path, path)
        return await self.sharing.get_link_by_file_id(file.id)

    async def get_link_thumbnail(
        self, token: str, *, size: int
    ) -> tuple[AnyFile, bytes]:
        link = await self.sharing.get_link_by_token(token)
        return cast(
            tuple[AnyFile, bytes],
            await self.file_service.thumbnail(link.file_id, size=size)
        )

    async def get_shared_item(self, token: str) -> File:
        link = await self.sharing.get_link_by_token(token)
        return await self.filecore.get_by_id(link.file_id)

    async def revoke_link(self, token: str) -> None:
        await self.sharing.revoke_link(token)
