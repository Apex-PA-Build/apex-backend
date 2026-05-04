from typing import Any
from app.core.supabase import get_client
from app.core.logging import get_logger

logger = get_logger(__name__)


async def _get_or_create_list(client: Any, user_id: str, name: str, list_type: str = "general") -> str:
    result = await (
        client.table("lists")
        .select("id")
        .eq("user_id", user_id)
        .ilike("name", f"%{name}%")
        .limit(1)
        .execute()
    )
    if result.data:
        return result.data[0]["id"]
    created = await client.table("lists").insert({"user_id": user_id, "name": name, "type": list_type}).execute()
    return created.data[0]["id"]


async def add_item(user_id: str, list_name: str, item: str, list_type: str = "general") -> dict[str, Any]:
    client = await get_client()
    list_id = await _get_or_create_list(client, user_id, list_name, list_type)
    result = await client.table("list_items").insert({"list_id": list_id, "user_id": user_id, "text": item}).execute()
    logger.info("list_item_added", list=list_name, item=item)
    return {"list": list_name, "item": item, "added": True}


async def get_list(user_id: str, list_name: str) -> dict[str, Any]:
    client = await get_client()
    list_result = await (
        client.table("lists")
        .select("id, name, type")
        .eq("user_id", user_id)
        .ilike("name", f"%{list_name}%")
        .limit(1)
        .execute()
    )
    if not list_result.data:
        return {"list": list_name, "items": []}

    lst = list_result.data[0]
    items = await (
        client.table("list_items")
        .select("id, text, checked")
        .eq("list_id", lst["id"])
        .order("created_at")
        .execute()
    )
    return {"list": lst["name"], "type": lst["type"], "items": items.data or []}


async def check_item(user_id: str, list_name: str, item_text: str) -> dict[str, Any]:
    client = await get_client()
    list_result = await (
        client.table("lists")
        .select("id")
        .eq("user_id", user_id)
        .ilike("name", f"%{list_name}%")
        .limit(1)
        .execute()
    )
    if not list_result.data:
        return {"error": f"List '{list_name}' not found"}

    await (
        client.table("list_items")
        .update({"checked": True})
        .eq("list_id", list_result.data[0]["id"])
        .ilike("text", f"%{item_text}%")
        .execute()
    )
    return {"checked": True, "item": item_text}


async def clear_list(user_id: str, list_name: str) -> dict[str, Any]:
    client = await get_client()
    list_result = await (
        client.table("lists")
        .select("id")
        .eq("user_id", user_id)
        .ilike("name", f"%{list_name}%")
        .limit(1)
        .execute()
    )
    if not list_result.data:
        return {"error": f"List '{list_name}' not found"}

    await client.table("list_items").delete().eq("list_id", list_result.data[0]["id"]).execute()
    return {"cleared": True, "list": list_name}
