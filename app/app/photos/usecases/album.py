from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from app.app.photos.domain import Album

if TYPE_CHECKING:
    from uuid import UUID

    class IUseCaseServices(Protocol):
        ...

__all__ = [
    "AlbumUseCase",
]


class AlbumUseCase:
    __slots__: list[str] = []

    def __init__(self, services: IUseCaseServices):
        ...

    async def create(self, title: str, owner_id: UUID) -> Album:
        """Creates a new album."""
        from app.toolkit import timezone

        return Album(
            id=UUID('b0f4abc4-be87-4c48-9a11-c89b9a7d44f9'),
            owner_id=UUID('90b1b96f-fb2b-42ba-b07f-85367a38b8ef'),
            title='New Album',
            created_at=timezone.now(),
            cover=None,
        )

    async def list_(
        self,
        user_id: UUID,
        *,
        offset: int,
        limit: int = 25,
    ) -> list[Album]:
        """Lists albums for given user."""
        return []
