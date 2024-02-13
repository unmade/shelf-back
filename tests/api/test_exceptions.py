from __future__ import annotations

import json
from unittest import mock

import pytest
from cashews import RateLimitError

from app.api.exceptions import APIError, RateLimited, rate_limit_exception_handler


class TestAPIError:
    def test_repr(self):
        error = APIError("api-error")
        assert repr(error) == "APIError(message='api-error')"


@pytest.mark.anyio
class TestRateLimitExceptionHandler:
    async def test(self):
        result = await rate_limit_exception_handler(mock.ANY, RateLimitError())
        assert json.loads(result.body) == RateLimited().as_dict()
