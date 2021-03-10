from __future__ import annotations

from typing import Optional, TypedDict

from fastapi.responses import JSONResponse


class APIErrorDict(TypedDict):
    code: str
    message: str
    reason: str


class APIError(Exception):
    status_code = 500
    default_code = "SERVER_ERROR"
    default_message = "A server error occurred"
    default_reason = "Something has gone wrong on the server"

    def __init__(
        self,
        message: Optional[str] = None,
        reason: Optional[str] = None,
        code: Optional[str] = None,
    ):
        self.message = message or self.default_message
        self.reason = reason or self.default_reason
        self.code = code or self.default_code
        super().__init__()

    def __repr__(self):
        return (
            f"{self.__class__.__name__}("
            f"code='{self.code}',"
            f"message='{self.message}',"
            f"reason='{self.reason}',"
            f")"
        )

    def as_dict(self) -> APIErrorDict:
        return {
            "code": self.code,
            "reason": self.reason,
            "message": self.message,
        }


async def api_error_exception_handler(_, exc: APIError):
    return JSONResponse(exc.as_dict(), status_code=exc.status_code)


class MissingToken(APIError):
    status_code = 401
    default_code = "MISSING_TOKEN"
    default_message = "Missing token"
    reason = "No token found in the authorization header"


class InvalidToken(APIError):
    status_code = 403
    default_code = "INVALID_TOKEN"
    default_message = "Invalid token"
    default_reason = "Could not validate credentials"


class UserNotFound(APIError):
    status_code = 404
    default_code = "USER_NOT_FOUND"
    default_message = "User not found"
