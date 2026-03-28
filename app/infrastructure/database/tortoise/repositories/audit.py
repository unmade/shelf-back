from __future__ import annotations

from app.app.audit.domain import AuditTrail
from app.app.audit.repositories import IAuditTrailRepository
from app.infrastructure.database.tortoise import models

__all__ = ["AuditTrailRepository"]


class AuditTrailRepository(IAuditTrailRepository):
    async def save(self, audit_trail: AuditTrail) -> AuditTrail:
        action, _ = await models.AuditTrailAction.get_or_create(
            name=audit_trail.action,
        )

        obj = await models.AuditTrail.create(
            action=action,
            user_id=audit_trail.user.id if audit_trail.user else None,
            created_at=audit_trail.created_at,
        )

        if audit_trail.asset:
            await models.AuditTrailAsset.create(
                audit_trail=obj,
                file_id=audit_trail.asset.id,
            )

        return audit_trail.model_copy(update={"id": obj.id})
