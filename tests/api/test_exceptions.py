from __future__ import annotations

from unittest import mock

import pytest
from cashews import RateLimitError

from app.api.exceptions import APIError, RateLimited, rate_limit_exception_handler
from app.toolkit import json_


class TestAPIError:
    def test_repr(self):
        error = APIError("api-error")
        assert repr(error) == "APIError(message='api-error')"


@pytest.mark.anyio
class TestRateLimitExceptionHandler:
    async def test(self):
        result = await rate_limit_exception_handler(mock.ANY, RateLimitError())
        assert json_.loads(result.body) == RateLimited().as_dict()
