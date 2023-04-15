from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from app.app.audit.domain import AuditTrail
from app.app.audit.domain.current_user_context import current_user_ctx
from app.app.infrastructure.database import SENTINEL_ID

if TYPE_CHECKING:
    from app.app.audit.domain.audit import AuditTrailAction
    from app.app.audit.repositories import IAuditTrailRepository
    from app.app.files.domain import File
    from app.app.users.domain import User

    class IServiceDatabase(Protocol):
        audit_trail: IAuditTrailRepository


class AuditTrailService:
    __slots__ = ("db",)

    def __init__(self, database: IServiceDatabase) -> None:
        self.db = database

    async def _track_file_action(self, action: AuditTrailAction, file: File) -> None:
        ctx = current_user_ctx.get()
        await self.db.audit_trail.save(
            AuditTrail(
                id=SENTINEL_ID,
                action=action,
                user=AuditTrail.User(
                    id=str(ctx.user.id),
                    username=ctx.user.username,
                ),
                asset=AuditTrail.File(
                    id=file.id,
                    name=file.name,
                    path=str(file.path),
                ),
            )
        )

    async def _track_user_action(self, action: AuditTrailAction) -> None:
        ctx = current_user_ctx.get()
        await self.db.audit_trail.save(
            AuditTrail(
                id=SENTINEL_ID,
                action=action,
                user=AuditTrail.User(
                    id=str(ctx.user.id),
                    username=ctx.user.username,
                ),
            )
        )

    async def file_added(self, file: File) -> None:
        await self._track_file_action(AuditTrail.Action.file_added, file=file)

    async def file_moved(self, file: File) -> None:
        await self._track_file_action(AuditTrail.Action.file_moved, file=file)

    async def file_trashed(self, file: File) -> None:
        await self._track_file_action(AuditTrail.Action.file_trashed, file=file)

    async def folder_created(self, file: File) -> None:
        await self._track_file_action(AuditTrail.Action.folder_created, file=file)

    async def trash_emptied(self) -> None:
        await self._track_user_action(AuditTrail.Action.trash_emptied)

    async def user_signed_in(self, user: User) -> None:
        await self.db.audit_trail.save(
            AuditTrail(
                id=SENTINEL_ID,
                action=AuditTrail.Action.user_signed_in,
                user=AuditTrail.User(
                    id=str(user.id),
                    username=user.username,
                ),
            )
        )
