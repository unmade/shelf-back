from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from app.app.audit.domain import AuditTrail

__all__ = ["IAuditTrailRepository"]


class IAuditTrailRepository(Protocol):
    async def save(self, audit_trail: AuditTrail) -> AuditTrail:
        """
        Saves a new audit trail.

        Args:
            audit_trail (audit_trail): an AuditTrail instance to be saved.

        Returns:
            AuditTrail: Saved audit trail.
        """
