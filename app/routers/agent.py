from typing import Any

from fastapi import APIRouter, Query, Request

from app.middleware.auth import get_user_id
from app.schemas.agent import AgentMessageRead, AgentPropose, AgentRespond
from app.services import agent as agent_svc

router = APIRouter()


@router.get("", response_model=list[AgentMessageRead])
async def get_messages(
    request: Request,
    direction: str = Query("inbox", description="inbox | sent"),
) -> Any:
    user_id = get_user_id(request)
    return await agent_svc.get_messages(user_id, direction=direction)


@router.post("/propose", response_model=AgentMessageRead, status_code=201)
async def propose(request: Request, body: AgentPropose) -> Any:
    user_id = get_user_id(request)
    return await agent_svc.send_message(
        from_user_id=user_id,
        to_user_id=body.to_user_id,
        message_type=body.message_type,
        content=body.content,
    )


@router.post("/{message_id}/respond", response_model=AgentMessageRead)
async def respond(request: Request, message_id: str, body: AgentRespond) -> Any:
    user_id = get_user_id(request)
    return await agent_svc.respond(user_id, message_id, body.status, body.counter_content)
