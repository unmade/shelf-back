from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from app.app.audit.domain import AuditTrail
from app.app.infrastructure.database import SENTINEL_ID

pytestmark = [pytest.mark.anyio, pytest.mark.database]


if TYPE_CHECKING:
    from app.app.files.domain import File
    from app.app.users.domain import User
    from app.infrastructure.database.edgedb.repositories import AuditTrailRepository


class TestSave:
    async def test(self, audit_trail_repo: AuditTrailRepository, user: User):
        # GIVEN
        created_at = datetime(2022, 8, 14, 16, 13, tzinfo=UTC)
        audit_trail = AuditTrail(
            id=SENTINEL_ID,
            action=AuditTrail.Action.user_signed_in,
            user=AuditTrail.User(
                id=user.id,
                username=user.username,
            ),
            created_at=created_at,
        )
        # WHEN: action does not exists
        saved_trail = await audit_trail_repo.save(audit_trail)
        # THEN: action is created
        assert saved_trail.id != SENTINEL_ID
        audit_trail.id = saved_trail.id
        assert saved_trail == audit_trail

        # WHEN: action exists
        saved_trail = await audit_trail_repo.save(audit_trail)
        # THEN: action is selected
        assert saved_trail.id != SENTINEL_ID
        audit_trail.id = saved_trail.id
        assert saved_trail == audit_trail

    async def test_saving_asset(
        self,
        audit_trail_repo: AuditTrailRepository,
        user: User,
        file: File,
    ):
        # GIVEN
        created_at = datetime(2022, 8, 14, 16, 13, tzinfo=UTC)
        audit_trail = AuditTrail(
            id=SENTINEL_ID,
            action=AuditTrail.Action.user_signed_in,
            user=AuditTrail.User(
                id=user.id,
                username=user.username,
            ),
            asset=AuditTrail.File(
                id=file.id,
                name=file.name,
                path=str(file.path),
            ),
            created_at=created_at,
        )
        # WHEN
        saved_trail = await audit_trail_repo.save(audit_trail)
        # THEN
        assert saved_trail.id != SENTINEL_ID
        audit_trail.id = saved_trail.id
        assert saved_trail == audit_trail

        obj = await audit_trail_repo.conn.query_required_single(
            "select AuditTrail { assets } filter .id = <uuid>$id",
            id=saved_trail.id
        )
        assert len(obj.assets) == 1
        assert obj.assets[0].id == file.id
