from __future__ import annotations

from typing import TYPE_CHECKING, cast

from app.app.files.domain import File
from app.app.files.services import FileCoreService, SharingService

if TYPE_CHECKING:
    from app.app.files.domain import SharedLink
    from app.typedefs import StrOrPath

__all__ = ["SharingManager"]


class SharingManager:
    __slots__ = ["filecore", "sharing"]

    def __init__(self, filecore: FileCoreService, sharing: SharingService):
        self.filecore = filecore
        self.sharing = sharing

    async def create_link(self, ns_path: str, path: StrOrPath) -> SharedLink:
        file = await self.filecore.get_by_path(ns_path, path)
        return await self.sharing.create_link(file.id)

    async def get_link(self, ns_path: str, path: StrOrPath) -> SharedLink:
        file = await self.filecore.get_by_path(ns_path, path)
        return await self.sharing.get_link_by_file_id(file.id)

    async def get_link_thumbnail(self, token: str, *, size: int) -> tuple[File, bytes]:
        link = await self.sharing.get_link_by_token(token)
        return cast(
            tuple[File, bytes],
            await self.filecore.thumbnail(link.file_id, size=size),
        )

    async def get_shared_item(self, token: str) -> File:
        link = await self.sharing.get_link_by_token(token)
        return await self.filecore.get_by_id(link.file_id)

    async def revoke_link(self, token: str) -> None:
        await self.sharing.revoke_link(token)
