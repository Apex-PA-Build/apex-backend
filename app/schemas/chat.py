from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None  # for multi-turn memory within a session


class ChatResponse(BaseModel):
    reply: str
    tools_used: list[str] = []
