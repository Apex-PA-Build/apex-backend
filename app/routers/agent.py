from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthError
from app.db.session import get_db
from app.schemas.agent import (
    AgentMessageRead,
    AgentRespondRequest,
    NegotiationProposal,
)
from app.services.agent_service import (
    get_all_messages,
    propose_negotiation,
    respond_to_message,
    send_message,
)
from app.schemas.agent import AgentMessageCreate

router = APIRouter()


def _uid(request: Request) -> str:
    uid: str | None = getattr(request.state, "user_id", None)
    if not uid:
        raise AuthError("Not authenticated")
    return uid


@router.get("/messages", response_model=list[AgentMessageRead])
async def get_messages(
    request: Request, db: AsyncSession = Depends(get_db)
) -> list[AgentMessageRead]:
    """Get all agent messages (sent and received) for the current user."""
    msgs = await get_all_messages(_uid(request), db)
    return [AgentMessageRead.model_validate(m) for m in msgs]


@router.post("/propose", response_model=AgentMessageRead, status_code=201)
async def propose(
    data: NegotiationProposal,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> AgentMessageRead:
    """Initiate a scheduling or financial negotiation with another user's APEX."""
    msg = await propose_negotiation(_uid(request), data, db)
    return AgentMessageRead.model_validate(msg)


@router.post("/respond", response_model=AgentMessageRead)
async def respond(
    data: AgentRespondRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> AgentMessageRead:
    """Accept, decline, or counter-propose an inbound agent message."""
    msg = await respond_to_message(_uid(request), data, db)
    return AgentMessageRead.model_validate(msg)


@router.post("/send", response_model=AgentMessageRead, status_code=201)
async def send_agent_message(
    data: AgentMessageCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> AgentMessageRead:
    """Send a raw agent message to another user's APEX."""
    msg = await send_message(_uid(request), data, db)
    return AgentMessageRead.model_validate(msg)
