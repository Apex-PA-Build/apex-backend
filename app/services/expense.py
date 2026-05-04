from typing import Any
from app.core.supabase import get_client
from app.core.logging import get_logger
from app.utils.datetime import utcnow

logger = get_logger(__name__)


async def log(user_id: str, data: dict[str, Any]) -> dict[str, Any]:
    client = await get_client()
    payload = {k: v for k, v in data.items() if v is not None}
    payload["user_id"] = user_id
    result = await client.table("expenses").insert(payload).execute()
    logger.info("expense_logged", amount=data.get("amount"), category=data.get("category"))
    return result.data[0]


async def summary(user_id: str, days: int = 30) -> dict[str, Any]:
    from datetime import timedelta
    client = await get_client()
    since = (utcnow() - timedelta(days=days)).isoformat()
    result = await (
        client.table("expenses")
        .select("amount, category, description, expense_at")
        .eq("user_id", user_id)
        .gte("expense_at", since)
        .order("expense_at", desc=True)
        .execute()
    )
    rows = result.data or []
    total = sum(float(r["amount"]) for r in rows)
    by_category: dict[str, float] = {}
    for r in rows:
        by_category[r["category"]] = by_category.get(r["category"], 0) + float(r["amount"])
    return {"total": total, "days": days, "by_category": by_category, "transactions": rows}


async def add_subscription(user_id: str, data: dict[str, Any]) -> dict[str, Any]:
    client = await get_client()
    payload = {k: v for k, v in data.items() if v is not None}
    payload["user_id"] = user_id
    result = await client.table("subscriptions").insert(payload).execute()
    return result.data[0]


async def list_subscriptions(user_id: str) -> list[dict[str, Any]]:
    client = await get_client()
    result = await (
        client.table("subscriptions")
        .select("*")
        .eq("user_id", user_id)
        .eq("is_active", True)
        .order("next_due")
        .execute()
    )
    return result.data or []


async def track_owed(user_id: str, person: str, amount: float, direction: str, reason: str) -> dict[str, Any]:
    """direction: 'they_owe_me' or 'i_owe_them'"""
    from app.services.memory import store
    content = f"{person} owes me ₹{amount} for {reason}" if direction == "they_owe_me" else f"I owe {person} ₹{amount} for {reason}"
    mem = await store(user_id, content, "fact", source="user_explicit")
    return {"tracked": True, "content": content, "memory_id": mem["id"]}


async def get_owed(user_id: str) -> list[dict[str, Any]]:
    from app.services.memory import list_memories
    mems = await list_memories(user_id, category="fact")
    return [m for m in mems if "owes" in m["content"].lower()]
