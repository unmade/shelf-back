from app.api.exceptions import APIError


class EmailAlreadyTaken(APIError):
    status_code = 400
    code = "EMAIL_ALREADY_TAKEN"
    code_verbose = "Email already taken"
    default_message = "Email is already taken by other user"


class EmailUpdateStarted(APIError):
    status_code = 400
    code = "EMAIL_UPDATE_STARTED"
    code_verbose = "Email update started"
    default_message = "Email update in progress"


class EmailUpdateNotStarted(APIError):
    status_code = 400
    code = "EMAIL_UPDATE_NOT_STARTED"
    code_verbose = "Email update not started"
    default_message = "You should call change email first"
