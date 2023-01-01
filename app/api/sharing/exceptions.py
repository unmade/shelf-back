from app.api.exceptions import APIError


class SharedLinkNotFound(APIError):
    status_code = 404
    code = "SHARED_LINK_NOT_FOUND"
    code_verbose = "Shared link not found"
    default_message = "Shared link is expired or doesn't exist"
