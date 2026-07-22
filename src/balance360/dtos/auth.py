from pydantic import BaseModel


class Auth(BaseModel):
    cuit: str
    token: str
    sign: str
