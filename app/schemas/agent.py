from typing import Any

from pydantic import BaseModel


class AgentMessageRead(BaseModel):
    id: str
    from_user_id: str
    to_user_id: str
    message_type: str
    content: dict[str, Any]
    status: str
    thread_id: str | None
    created_at: str


class AgentPropose(BaseModel):
    to_user_id: str
    message_type: str  # scheduling_request | financial_settle | follow_up_nudge
    content: dict[str, Any]


class AgentRespond(BaseModel):
    status: str  # accepted | declined | negotiating
    counter_content: dict[str, Any] | None = None
