from __future__ import annotations

from app.api.exceptions import APIError


class UserAlreadyExists(APIError):
    status_code = 400
    code = "USER_ALREADY_EXISTS"
    code_verbose = "User already exists"
    default_message = "Username or email is already taken by other user"
