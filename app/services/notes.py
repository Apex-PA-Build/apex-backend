from typing import Any
from app.core.supabase import get_client
from app.core.logging import get_logger

logger = get_logger(__name__)


async def create(user_id: str, data: dict[str, Any]) -> dict[str, Any]:
    client = await get_client()
    payload = {k: v for k, v in data.items() if v is not None}
    payload["user_id"] = user_id
    result = await client.table("notes").insert(payload).execute()
    logger.info("note_created", title=data.get("title", "untitled"))
    return result.data[0]


async def search(user_id: str, query: str) -> list[dict[str, Any]]:
    client = await get_client()
    result = await (
        client.table("notes")
        .select("id, title, content, tags, created_at")
        .eq("user_id", user_id)
        .or_(f"title.ilike.%{query}%,content.ilike.%{query}%")
        .order("created_at", desc=True)
        .limit(10)
        .execute()
    )
    return result.data or []


async def list_notes(user_id: str, limit: int = 20) -> list[dict[str, Any]]:
    client = await get_client()
    result = await (
        client.table("notes")
        .select("id, title, content, tags, pinned, created_at")
        .eq("user_id", user_id)
        .order("pinned", desc=True)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return result.data or []


async def append(user_id: str, note_title: str, content: str) -> dict[str, Any]:
    client = await get_client()
    result = await (
        client.table("notes")
        .select("id, content")
        .eq("user_id", user_id)
        .ilike("title", f"%{note_title}%")
        .limit(1)
        .execute()
    )
    if not result.data:
        return {"error": f"No note found matching '{note_title}'"}
    note = result.data[0]
    new_content = f"{note['content']}\n\n{content}"
    updated = await (
        client.table("notes")
        .update({"content": new_content})
        .eq("id", note["id"])
        .execute()
    )
    return updated.data[0]


async def delete(user_id: str, note_title: str) -> dict[str, Any]:
    client = await get_client()
    result = await (
        client.table("notes")
        .delete()
        .eq("user_id", user_id)
        .ilike("title", f"%{note_title}%")
        .execute()
    )
    return {"deleted": bool(result.data)}
