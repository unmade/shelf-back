from app.api.exceptions import APIError


class AlreadyDeleted(APIError):
    status_code = 400
    default_code = "ALREADY_DELETED"
    default_message = "Already deleted."


class AlreadyExists(APIError):
    status_code = 400
    default_code = "ALREADY_EXISTS"
    default_message = "Already exists."


class DownloadNotFound(APIError):
    status_code = 404
    default_code = "DOWNLOAD_NOT_FOUND"
    default_message = "Download not found."


class InvalidPath(APIError):
    status_code = 400
    default_code = "INVALID_PATH"
    default_message = "Invalid path."


class PathNotFound(APIError):
    status_code = 404
    default_code = "PATH_NOT_FOUND"
    default_message = "Path not found."
