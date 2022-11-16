from app.api.exceptions import APIError


class InvalidCredentials(APIError):
    status_code = 401
    code = "INVALID_CREDENTIALS"
    code_verbose = "Invalid credentials"
    default_message = "Incorrect email or password"


class SignUpDisabled(APIError):
    status_code = 400
    code = "SIGN_UP_DISABLED"
    code_verbose = "Sign Up Disabled"
    default_message = "Sign up is closed for new users"


class UserAlreadyExists(APIError):
    status_code = 400
    code = "USER_ALREADY_EXISTS"
    code_verbose = "User already exists"
    default_message = "Username or email is already taken by other user"
