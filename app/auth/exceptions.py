from app.errors import APIError


class InvalidToken(APIError):
    status_code = 403
    default_code = "INVALID_TOKEN"
    default_message = "Could not validate credentials."


class UserNotFound(APIError):
    status_code = 404
    default_code = "USER_NOT_FOUND"
    default_message = "User not found."
