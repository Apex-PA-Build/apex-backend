from pydantic import BaseModel


class MessageResponse(BaseModel):
    message: str


class IDResponse(BaseModel):
    id: str
