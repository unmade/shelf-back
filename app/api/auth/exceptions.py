from app.api.exceptions import APIError


class InvalidCredentials(APIError):
    status_code = 401
    default_code = "INVALID_CREDENTIALS"
    default_message = "Invalid credentials"
    default_reason = "Incorrect email or password"
