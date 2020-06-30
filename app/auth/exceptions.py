from fastapi import HTTPException


class UserNotFound(HTTPException):
    def __init__(self):
        super().__init__(status_code=404, detail={"code": "USER_NOT_FOUND"})
