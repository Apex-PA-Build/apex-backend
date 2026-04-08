import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AgentMessageCreate(BaseModel):
    to_user_id: uuid.UUID
    message_type: str = Field(
        pattern="^(scheduling_request|financial_settle|follow_up_nudge|information_request)$"
    )
    content: dict[str, Any]
    thread_id: uuid.UUID | None = None


class AgentMessageRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    from_user_id: uuid.UUID
    to_user_id: uuid.UUID
    message_type: str
    content: dict[str, Any]
    status: str
    thread_id: uuid.UUID | None
    resolved_at: datetime | None
    created_at: datetime


class NegotiationProposal(BaseModel):
    """Propose a scheduling slot or financial settlement."""
    to_user_id: uuid.UUID
    proposal_type: str = Field(pattern="^(scheduling|financial)$")
    slots: list[dict[str, Any]] | None = None          # for scheduling
    amount: float | None = None                         # for financial
    currency: str | None = Field(default=None, max_length=8)
    note: str | None = Field(default=None, max_length=500)


class AgentRespondRequest(BaseModel):
    message_id: uuid.UUID
    decision: str = Field(pattern="^(accept|decline|counter)$")
    counter_content: dict[str, Any] | None = None
    note: str | None = Field(default=None, max_length=500)


class ConnectedUser(BaseModel):
    user_id: uuid.UUID
    name: str
    recent_interactions: int
    last_interaction_at: datetime | None
