from __future__ import annotations

from app.api.exceptions import APIError


class FileNotFound(APIError):
    status_code = 404
    code = "FILE_NOT_FOUND"
    code_verbose = "File not found"
    default_message = "File does not exists"


class UserEmailAlreadyVerified(APIError):
    status_code = 400
    code = "USER_EMAIL_ALREADY_VERIFIED"
    code_verbose = "User email already verified"
    default_message = ""


class UserEmailIsMissing(APIError):
    status_code = 400
    code = "USER_EMAIL_IS_MISSING"
    code_verbose = "User email is missing"
    default_message = "There is no email for the user"
