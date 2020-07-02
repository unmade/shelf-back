from __future__ import annotations

from typing import Optional

from fastapi.responses import JSONResponse


class APIError(Exception):
    status_code = 500
    default_code = "SERVER_ERROR"
    default_message = "A server error occurred."

    def __init__(
        self, message: Optional[str] = None, code: Optional[str] = None,
    ):
        self.message = message or self.default_message
        self.code = code or self.default_code
        super().__init__()

    def __repr__(self):
        return (
            f"{self.__class__.__name__}("
            f"code='{self.code}',"
            f" message='{self.message}',"
            f" details={self.details}"
            f")"
        )

    def as_dict(self):
        return


async def api_error_exception_handler(_, exc: APIError):
    return JSONResponse(
        {"code": exc.code, "message": exc.message}, status_code=exc.status_code,
    )
