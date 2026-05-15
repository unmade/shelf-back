from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from app.app.files.domain import File
from app.config import config

if TYPE_CHECKING:
    from uuid import UUID

    from app.app.blobs.services import BlobThumbnailService
    from app.app.files.domain import SharedLink
    from app.app.files.services import FileService, SharingService
    from app.app.infrastructure.database import IAtomic
    from app.app.users.services import UserService
    from app.toolkit.mediatypes import MediaType

    class IUseCaseServices(IAtomic, Protocol):
        file: FileService
        sharing: SharingService
        thumbnailer: BlobThumbnailService
        user: UserService

__all__ = ["SharingUseCase"]


class SharingUseCase:
    __slots__ = (
        "_services",
        "file",
        "sharing",
        "thumbnailer",
        "user",
    )

    def __init__(self, services: IUseCaseServices):
        self._services = services
        self.file = services.file
        self.sharing = services.sharing
        self.thumbnailer = services.thumbnailer
        self.user = services.user

    async def create_link(self, ns_path: str, file_id: UUID) -> SharedLink:
        """Creates a shared link for a file at the given path."""
        if config.features.shared_links_enabled is False:
            user = await self.user.get_by_username(ns_path)
            if not user.superuser:
                raise File.ActionNotAllowed()

        file = await self.file.get_by_id(ns_path, file_id)
        return await self.sharing.create_link(file.id)

    async def get_link(self, ns_path: str, file_id: UUID) -> SharedLink:
        file = await self.file.get_by_id(ns_path, file_id)
        return await self.sharing.get_link_by_file_id(file.id)

    async def get_link_thumbnail(
        self, token: str, *, size: int
    ) -> tuple[File, bytes, MediaType]:
        link = await self.sharing.get_link_by_token(token)
        file = await self.file.filecore.get_by_id(link.file_id)
        assert file.blob_id is not None
        thumb = await self.thumbnailer.thumbnail(file.blob_id, file.chash, size)
        return file, *thumb

    async def get_shared_item(self, token: str) -> File:
        link = await self.sharing.get_link_by_token(token)
        return await self.file.filecore.get_by_id(link.file_id)

    async def list_shared_links(self, ns_path: str) -> list[SharedLink]:
        """List recent shared links in the given namespace."""
        return await self.sharing.list_links_by_ns(ns_path, limit=50)

    async def revoke_link(self, token: str) -> None:
        await self.sharing.revoke_link(token)
