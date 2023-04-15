from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import pytest
from dateutil import tz

from app.app.audit.domain import AuditTrail
from app.app.infrastructure.database import SENTINEL_ID

pytestmark = [pytest.mark.database]


if TYPE_CHECKING:
    from app.app.files.domain import File
    from app.app.users.domain import User
    from app.infrastructure.database.edgedb.repositories import AuditTrailRepository


class TestSave:
    async def test(self, audit_trail_repo: AuditTrailRepository, user: User):
        # GIVEN
        created_at = datetime(2022, 8, 14, 16, 13, tzinfo=tz.gettz("America/New_York"))
        audit_trail = AuditTrail(
            id=SENTINEL_ID,
            action=AuditTrail.Action.user_signed_in,
            user=AuditTrail.User(
                id=str(user.id),
                username=user.username,
            ),
            created_at=created_at,
        )
        # WHEN: action does not exists
        saved_trail = await audit_trail_repo.save(audit_trail)
        # THEN: action is created
        assert saved_trail.id != SENTINEL_ID
        assert saved_trail.dict(exclude={"id"}) == audit_trail.dict(exclude={"id"})

        # WHEN: action exists
        saved_trail = await audit_trail_repo.save(audit_trail)
        # THEN: action is selected
        assert saved_trail.id != SENTINEL_ID
        assert saved_trail.dict(exclude={"id"}) == audit_trail.dict(exclude={"id"})

    async def test_saving_asset(
        self,
        audit_trail_repo: AuditTrailRepository,
        user: User,
        file: File,
    ):
        # GIVEN
        created_at = datetime(2022, 8, 14, 16, 13, tzinfo=tz.gettz("America/New_York"))
        audit_trail = AuditTrail(
            id=SENTINEL_ID,
            action=AuditTrail.Action.user_signed_in,
            user=AuditTrail.User(
                id=str(user.id),
                username=user.username,
            ),
            asset=AuditTrail.File(
                id=str(file.id),
                name=file.name,
                path=str(file.path),
            ),
            created_at=created_at,
        )
        # WHEN
        saved_trail = await audit_trail_repo.save(audit_trail)
        # THEN
        assert saved_trail.id != SENTINEL_ID
        assert saved_trail.dict(exclude={"id"}) == audit_trail.dict(exclude={"id"})

        obj = await audit_trail_repo.conn.query_required_single(
            "select AuditTrail { assets } filter .id = <uuid>$id",
            id=saved_trail.id
        )
        assert len(obj.assets) == 1
        assert str(obj.assets[0].id) == file.id