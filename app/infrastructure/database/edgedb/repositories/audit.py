from __future__ import annotations

from typing import TYPE_CHECKING

from app.app.audit.domain import AuditTrail
from app.app.audit.repositories import IAuditTrailRepository

if TYPE_CHECKING:
    from app.infrastructure.database.edgedb.typedefs import GelAnyConn, GelContext

__all__ = ["AuditTrailRepository"]


class AuditTrailRepository(IAuditTrailRepository):
    __slots__ = ["db_context"]

    def __init__(self, db_context: GelContext):
        self.db_context = db_context

    @property
    def conn(self) -> GelAnyConn:
        return self.db_context.get()

    async def save(self, audit_trail: AuditTrail) -> AuditTrail:
        query = """
            WITH
                action := (
                    INSERT AuditTrailAction {
                        name := <str>$action
                    }
                    UNLESS CONFLICT ON .name
                    ELSE (
                        SELECT
                            AuditTrailAction
                    )
                ),
                asset := (
                    SELECT
                        Auditable
                    FILTER
                        .id = <OPTIONAL uuid>$asset_id
                ),
                user := (
                    SELECT
                        User
                    FILTER
                        .id = <uuid>$user_id
                ),
            SELECT (
                INSERT AuditTrail {
                    action := action,
                    user := user,
                    assets := asset,
                    created_at := <datetime>$created_at,
                }
            ) { id }
        """

        obj = await self.conn.query_required_single(
            query,
            action=audit_trail.action,
            user_id=audit_trail.user and audit_trail.user.id,
            asset_id=audit_trail.asset and audit_trail.asset.id,
            created_at=audit_trail.created_at,
        )

        return audit_trail.model_copy(update={"id": obj.id})
