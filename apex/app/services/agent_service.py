import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import publish
from app.core.exceptions import ForbiddenError, NotFoundError
from app.core.logging import get_logger
from app.models.agent_message import AgentMessage
from app.schemas.agent import AgentMessageCreate, AgentRespondRequest, NegotiationProposal
from app.services.llm_service import chat

logger = get_logger(__name__)


async def send_message(
    from_user_id: str,
    data: AgentMessageCreate,
    db: AsyncSession,
) -> AgentMessage:
    msg = AgentMessage(
        from_user_id=uuid.UUID(from_user_id),
        to_user_id=data.to_user_id,
        message_type=data.message_type,
        content=data.content,
        thread_id=data.thread_id or uuid.uuid4(),
    )
    db.add(msg)
    await db.flush()

    # Notify recipient over Redis pub/sub → WebSocket
    await publish(
        f"agent:{data.to_user_id}",
        {
            "event": "new_agent_message",
            "message_id": str(msg.id),
            "from_user_id": from_user_id,
            "message_type": data.message_type,
        },
    )
    logger.info(
        "agent_message_sent",
        from_user=from_user_id,
        to_user=str(data.to_user_id),
        type=data.message_type,
    )
    return msg


async def get_pending_messages(user_id: str, db: AsyncSession) -> list[AgentMessage]:
    result = await db.execute(
        select(AgentMessage)
        .where(
            AgentMessage.to_user_id == uuid.UUID(user_id),
            AgentMessage.status.in_(["pending", "negotiating"]),
        )
        .order_by(AgentMessage.created_at.desc())
    )
    return list(result.scalars().all())


async def get_all_messages(user_id: str, db: AsyncSession) -> list[AgentMessage]:
    result = await db.execute(
        select(AgentMessage)
        .where(
            or_(
                AgentMessage.from_user_id == uuid.UUID(user_id),
                AgentMessage.to_user_id == uuid.UUID(user_id),
            )
        )
        .order_by(AgentMessage.created_at.desc())
        .limit(50)
    )
    return list(result.scalars().all())


async def respond_to_message(
    user_id: str,
    data: AgentRespondRequest,
    db: AsyncSession,
) -> AgentMessage:
    result = await db.execute(
        select(AgentMessage).where(AgentMessage.id == data.message_id)
    )
    msg = result.scalar_one_or_none()
    if not msg:
        raise NotFoundError(f"Message {data.message_id} not found")
    if str(msg.to_user_id) != user_id:
        raise ForbiddenError("You cannot respond to this message")

    if data.decision == "accept":
        msg.status = "accepted"
        msg.resolved_at = datetime.now(timezone.utc)
    elif data.decision == "decline":
        msg.status = "declined"
        msg.resolved_at = datetime.now(timezone.utc)
    elif data.decision == "counter":
        msg.status = "negotiating"
        # Create counter-proposal as new message in same thread
        counter = AgentMessage(
            from_user_id=uuid.UUID(user_id),
            to_user_id=msg.from_user_id,
            message_type=msg.message_type,
            content=data.counter_content or {},
            thread_id=msg.thread_id,
        )
        db.add(counter)

    await publish(
        f"agent:{msg.from_user_id}",
        {
            "event": "agent_message_response",
            "message_id": str(msg.id),
            "decision": data.decision,
            "from_user_id": user_id,
        },
    )
    return msg


async def propose_negotiation(
    from_user_id: str,
    data: NegotiationProposal,
    db: AsyncSession,
) -> AgentMessage:
    content: dict[str, Any] = {"proposal_type": data.proposal_type}
    if data.proposal_type == "scheduling":
        content["slots"] = data.slots or []
        content["note"] = data.note
    elif data.proposal_type == "financial":
        content["amount"] = data.amount
        content["currency"] = data.currency
        content["note"] = data.note

    return await send_message(
        from_user_id=from_user_id,
        data=AgentMessageCreate(
            to_user_id=data.to_user_id,
            message_type="scheduling_request" if data.proposal_type == "scheduling" else "financial_settle",
            content=content,
        ),
        db=db,
    )


async def auto_respond_if_enabled(
    msg: AgentMessage,
    to_user: Any,
    db: AsyncSession,
) -> None:
    """Optionally have APEX auto-respond to simple scheduling requests."""
    from app.core.config import settings
    if not settings.agent_auto_respond:
        return
    if msg.message_type != "scheduling_request":
        return

    response = await chat(
        messages=[{
            "role": "user",
            "content": (
                f"A scheduling request was received: {msg.content}. "
                f"User {to_user.name} has these preferences: {to_user.preferences}. "
                "Should this be auto-accepted, declined, or does it need human review? "
                "Reply with one word: accept, decline, or review."
            ),
        }],
        temperature=0.0,
    )
    decision = response.strip().lower()
    if decision in ("accept", "decline"):
        await respond_to_message(
            str(msg.to_user_id),
            AgentRespondRequest(message_id=msg.id, decision=decision),
            db,
        )
