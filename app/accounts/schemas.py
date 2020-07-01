from pydantic import BaseModel


class Account(BaseModel):
    username: str

    class Config:
        orm_mode = True
