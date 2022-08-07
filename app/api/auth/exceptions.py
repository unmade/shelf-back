from app.api.exceptions import APIError


class InvalidCredentials(APIError):
    status_code = 401
    code = "INVALID_CREDENTIALS"
    code_verbose = "Invalid credentials"
    default_message = "Incorrect email or password"


class UserAlreadyExists(APIError):
    status_code = 400
    code = "USER_ALREADY_EXISTS"
    code_verbose = "User already exists"
    default_message = "Username or email is already taken by other user"
