from typing import Any

from app.core import cache
from app.core.exceptions import ForbiddenError, NotFoundError
from app.core.logging import get_logger
from app.core.supabase import get_client

logger = get_logger(__name__)


async def send_message(
    from_user_id: str,
    to_user_id: str,
    message_type: str,
    content: dict[str, Any],
    thread_id: str | None = None,
) -> dict[str, Any]:
    client = await get_client()
    result = await client.table("agent_messages").insert({
        "from_user_id": from_user_id,
        "to_user_id": to_user_id,
        "message_type": message_type,
        "content": content,
        "thread_id": thread_id,
        "status": "pending",
    }).execute()

    message = result.data[0]

    # Notify recipient via Redis pub/sub (WebSocket listener picks this up)
    await cache.publish(f"agent:{to_user_id}", {
        "event": "new_agent_message",
        "message": message,
    })

    logger.info("agent_message_sent", from_user_id=from_user_id, to_user_id=to_user_id, type=message_type)
    return message


async def get_messages(user_id: str, direction: str = "inbox") -> list[dict[str, Any]]:
    client = await get_client()
    if direction == "inbox":
        result = await (
            client.table("agent_messages")
            .select("*")
            .eq("to_user_id", user_id)
            .order("created_at", desc=True)
            .limit(50)
            .execute()
        )
    else:
        result = await (
            client.table("agent_messages")
            .select("*")
            .eq("from_user_id", user_id)
            .order("created_at", desc=True)
            .limit(50)
            .execute()
        )
    return result.data or []


async def respond(
    user_id: str,
    message_id: str,
    status: str,
    counter_content: dict[str, Any] | None = None,
) -> dict[str, Any]:
    client = await get_client()

    # Verify the message is addressed to this user
    result = await client.table("agent_messages").select("*").eq("id", message_id).execute()
    if not result.data:
        raise NotFoundError("Agent message")
    msg = result.data[0]
    if msg["to_user_id"] != user_id:
        raise ForbiddenError()

    from app.utils.datetime import utcnow
    update_payload: dict[str, Any] = {"status": status}
    if status == "accepted":
        update_payload["resolved_at"] = utcnow().isoformat()
    if counter_content:
        update_payload["content"] = {**msg["content"], "counter": counter_content}

    updated = await (
        client.table("agent_messages")
        .update(update_payload)
        .eq("id", message_id)
        .execute()
    )

    # Notify the original sender
    await cache.publish(f"agent:{msg['from_user_id']}", {
        "event": "agent_message_updated",
        "message": updated.data[0],
    })

    return updated.data[0]


async def get_pending_inbox_count(user_id: str) -> int:
    client = await get_client()
    result = await (
        client.table("agent_messages")
        .select("id", count="exact")
        .eq("to_user_id", user_id)
        .eq("status", "pending")
        .execute()
    )
    return result.count or 0
