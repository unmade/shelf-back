from __future__ import annotations

import pickle
import uuid
from typing import TYPE_CHECKING

import pytest

from app.app.audit.domain import CurrentUserContext
from app.app.audit.domain.current_user_context import current_user_ctx

if TYPE_CHECKING:
    from app.app.audit.domain.current_user_context import CurrentUser


def _make_user() -> CurrentUser:
    return CurrentUserContext.User(
        id=uuid.uuid4(),
        username="admin",
    )


class TestCurrentUserContext:
    def test_context_manager(self):
        user = _make_user()
        with CurrentUserContext(user=user) as ctx:
            assert isinstance(ctx, CurrentUserContext)
            assert current_user_ctx.get() == ctx
        with pytest.raises(LookupError):
            current_user_ctx.get()

    def test_pickling(self):
        # GIVEN
        user = _make_user()
        ctx = CurrentUserContext(user=user)
        # WHEN
        dump = pickle.dumps(ctx)
        # THEN
        assert pickle.loads(dump) == ctx
