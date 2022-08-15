from __future__ import annotations

import enum


class ErrorCode(str, enum.Enum):
    internal = "internal_error"
    file_already_exists = "file_already_exists"
    file_not_found = "file_not_found"
    file_metadata_already_exists = "file_metadata_already_exists"
    file_metadata_not_found = "file_metadata_not_found"
    fingerprint_already_exists = "fingerprint_already_exists"
    fingerprint_not_found = "fingerprint_not_found"
    is_a_directory = "is_a_directory"
    missing_parent = "missing_parent"
    not_a_directory = "not_a_directory"
    storage_quota_exceeded = "storage_quota_exceeded"


class Error(Exception):
    """Base class for all app-related errors"""

    code: ErrorCode


class FileAlreadyExists(Error):
    code = ErrorCode.file_already_exists


class FileNotFound(Error):
    code = ErrorCode.file_not_found


class FileMetadataAlreadyExists(Error):
    code = ErrorCode.file_metadata_already_exists


class FileMetadataNotFound(Error):
    code = ErrorCode.file_metadata_not_found


class FingerprintAlreadyExists(Error):
    code = ErrorCode.fingerprint_already_exists


class FingerprintNotFound(Error):
    code = ErrorCode.fingerprint_not_found


class IsADirectory(Error):
    code = ErrorCode.is_a_directory


class MissingParent(Error):
    code = ErrorCode.missing_parent


class NamespaceNotFound(Exception):
    pass


class NotADirectory(Error):
    code = ErrorCode.not_a_directory


class StorageQuotaExceeded(Error):
    code = ErrorCode.storage_quota_exceeded


class ThumbnailUnavailable(Exception):
    pass


class UserNotFound(Exception):
    pass


class UserAlreadyExists(Exception):
    pass
