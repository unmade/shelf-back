from app.api.exceptions import APIError


class PathNotFound(APIError):
    status_code = 404
    default_code = "PATH_NOT_FOUND"
    default_message = "Path not found."


class AlreadyExists(APIError):
    status_code = 400
    default_code = "ALREADY_EXISTS"
    default_message = "Already exists."


class DownloadNotFound(APIError):
    status_code = 404
    default_code = "DOWNLOAD_NOT_FOUND"
    default_message = "Download not found."


class InvalidOperation(APIError):
    status_code = 400
    default_code = "INVALID_OPERATION"
    default_message = "Invalid operation."


class AlreadyDeleted(APIError):
    status_code = 400
    default_code = "ALREADY_DELETED"
    default_message = "Already deleted."
