from __future__ import annotations

from app.api.exceptions import APIError


class FileNotFound(APIError):
    status_code = 404
    code = "FILE_NOT_FOUND"
    code_verbose = "File not found"
    default_message = "File does not exists"
