from app.api.exceptions import APIError


class FileMemberAlreadyExists(APIError):
    status_code = 400
    code = "FILE_MEMBER_ALREADY_EXISTS"
    code_verbose = "File member already exists"
    default_message = "User already a file member"


class SharedLinkNotFound(APIError):
    status_code = 404
    code = "SHARED_LINK_NOT_FOUND"
    code_verbose = "Shared link not found"
    default_message = "Shared link is expired or doesn't exist"
