from __future__ import annotations

import enum


class ErrorCode(str, enum.Enum):
    internal = "internal_error"
    file_already_exists = "file_already_exists"
    file_not_found = "file_not_found"
    file_metadata_not_found = "file_metadata_not_found"
    file_too_large = "file_too_large"
    fingerprint_already_exists = "fingerprint_already_exists"
    fingerprint_not_found = "fingerprint_not_found"
    is_a_directory = "is_a_directory"
    malformed_path = "malformed_path"
    missing_parent = "missing_parent"
    not_a_directory = "not_a_directory"
    shared_link_not_found = "shared_link_not_found"
    storage_quota_exceeded = "storage_quota_exceeded"


class Error(Exception):
    """Base class for all app-related errors"""

    code: ErrorCode


class StorageQuotaExceeded(Error):
    code = ErrorCode.storage_quota_exceeded


class ThumbnailUnavailable(Exception):
    pass


class UserNotFound(Exception):
    pass


class UserAlreadyExists(Exception):
    pass
