from app.api.exceptions import APIError


class InvalidCredentials(APIError):
    status_code = 401
    code = "INVALID_CREDENTIALS"
    code_verbose = "Invalid credentials"
    default_message = "Incorrect email or password"
