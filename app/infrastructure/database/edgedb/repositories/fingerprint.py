from __future__ import annotations

from typing import TYPE_CHECKING

from app import crud
from app.app.repositories import IFingerprintRepository

if TYPE_CHECKING:
    from app.domain.entities import Fingerprint
    from app.infrastructure.database.edgedb.typedefs import EdgeDBAnyConn, EdgeDBContext

__all__ = ["FingerprintRepository"]


class FingerprintRepository(IFingerprintRepository):
    def __init__(self, db_context: EdgeDBContext):
        self.db_context = db_context

    @property
    def conn(self) -> EdgeDBAnyConn:
        return self.db_context.get()

    async def save(self, fingerprint: Fingerprint) -> None:
        await crud.fingerprint.create(self.conn, fingerprint.file_id, fingerprint.value)
