from pydantic import BaseModel


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    user_id: int
    role: str
