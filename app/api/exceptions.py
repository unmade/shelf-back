from __future__ import annotations

from typing import TypedDict

from fastapi.responses import JSONResponse


class APIErrorDict(TypedDict):
    code: str
    code_verbose: str
    message: str


class APIError(Exception):
    status_code = 500
    code = "SERVER_ERROR"
    code_verbose = "A server error occurred"
    default_message = "Something has gone wrong on the server"

    def __init__(self, message: str | None = None):
        self.message = message or self.default_message

    def __repr__(self):
        return f"{self.__class__.__name__}(message={self.message!r})"

    def as_dict(self) -> APIErrorDict:
        return {
            "code": self.code,
            "code_verbose": self.code_verbose,
            "message": self.message,
        }


async def api_error_exception_handler(_, exc: APIError):
    return JSONResponse(exc.as_dict(), status_code=exc.status_code)


class MissingToken(APIError):
    status_code = 401
    code = "MISSING_TOKEN"
    code_verbose = "Missing token"
    default_message = "No token found in the authorization header"


class InvalidToken(APIError):
    status_code = 403
    code = "INVALID_TOKEN"
    code_verbose = "Invalid token"
    default_message = "Could not validate credentials"


class PermissionDenied(APIError):
    status_code = 403
    code = "PERMISSION_DENIED"
    code_verbose = "Permission Denied"
    default_message = "You don't have permission to perform the action requested"


class UserNotFound(APIError):
    status_code = 404
    code = "USER_NOT_FOUND"
    code_verbose = "User not found"
    default_message = ""
