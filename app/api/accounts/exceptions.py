from app.api.exceptions import APIError


class EmailAlreadyTaken(APIError):
    status_code = 400
    code = "EMAIL_ALREADY_TAKEN"
    code_verbose = "Email already taken"
    default_message = "Email is already taken by other user"


class EmailUpdateLimitReached(APIError):
    status_code = 400
    code = "EMAIL_UPDATE_LIMIT_REACHED"
    code_verbose = "Email update too frequent"
    default_message = "Email can be updated once every 6 hours"


class EmailUpdateNotStarted(APIError):
    status_code = 400
    code = "EMAIL_UPDATE_NOT_STARTED"
    code_verbose = "Email update not started"
    default_message = "Change email must be started first"


class EmailUpdateStarted(APIError):
    status_code = 400
    code = "EMAIL_UPDATE_STARTED"
    code_verbose = "Email update started"
    default_message = "Email update in progress"


class OTPCodeAlreadySent(APIError):
    status_code = 400
    code = "OTP_CODE_ALREADY_SENT"
    code_verbose = "OTP code was sent"
    default_message = "Please wait before requesting a new one"


class UserEmailAlreadyVerified(APIError):
    status_code = 400
    code = "USER_EMAIL_ALREADY_VERIFIED"
    code_verbose = "User email already verified"
    default_message = ""


class UserEmailIsMissing(APIError):
    status_code = 400
    code = "USER_EMAIL_IS_MISSING"
    code_verbose = "User email is missing"
    default_message = "There is no email for the user"
