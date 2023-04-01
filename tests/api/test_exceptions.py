from __future__ import annotations

from app.api.exceptions import APIError


class TestAPIError:
    def test_repr(self):
        error = APIError("api-error")
        assert repr(error) == "APIError(message='api-error')"
