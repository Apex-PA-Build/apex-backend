import json
from typing import Any

from app.core.logging import get_logger
from app.core.supabase import get_client
from app.services import embedding as emb
from app.services import llm
from app.utils.prompts import build_memory_extraction_prompt

logger = get_logger(__name__)


async def store(
    user_id: str,
    content: str,
    category: str,
    source: str = "conversation",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Embed a memory and store it in Supabase (content + vector)."""
    vectors = await emb.embed_documents([content])
    client = await get_client()
    result = await client.table("memories").insert({
        "user_id": user_id,
        "content": content,
        "category": category,
        "source": source,
        "embedding": vectors[0],
        "metadata": metadata or {},
    }).execute()
    logger.info("memory_stored", category=category, content=content[:60])
    return result.data[0]


async def search(user_id: str, query: str, limit: int = 10) -> list[dict[str, Any]]:
    """Semantic similarity search over a user's memories via pgvector RPC."""
    try:
        vector = await emb.embed_query(query)
        client = await get_client()
        result = await client.rpc("match_memories", {
            "query_embedding": vector,
            "match_user_id": user_id,
            "match_threshold": 0.4,
            "match_count": limit,
        }).execute()
        memories = result.data or []
        logger.info("memory_search", query=query[:50], found=len(memories))
        return memories
    except Exception as e:
        logger.warning("memory_search_failed", error=str(e))
        return []


async def list_memories(user_id: str, category: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    client = await get_client()
    query = (
        client.table("memories")
        .select("id, content, category, source, created_at")
        .eq("user_id", user_id)
        .eq("is_deleted", False)
        .order("created_at", desc=True)
        .limit(limit)
    )
    if category:
        query = query.eq("category", category)
    result = await query.execute()
    return result.data or []


async def delete(user_id: str, memory_id: str) -> None:
    client = await get_client()
    result = await (
        client.table("memories")
        .update({"is_deleted": True})
        .eq("id", memory_id)
        .eq("user_id", user_id)
        .execute()
    )
    if not result.data:
        from app.core.exceptions import NotFoundError
        raise NotFoundError("Memory")


async def extract_and_store(user_id: str, text: str, source: str = "conversation") -> list[dict[str, Any]]:
    """Use Claude Haiku to extract memories from text, then store them all."""
    if len(text.strip()) < 20:
        return []

    prompt = build_memory_extraction_prompt(text)
    try:
        extracted: list[dict[str, Any]] = await llm.extract_json(prompt)
    except Exception:
        logger.warning("memory_extraction_failed", user_id=user_id)
        return []

    if not isinstance(extracted, list):
        return []

    stored: list[dict[str, Any]] = []
    for item in extracted[:5]:
        content = item.get("content", "").strip()
        category = item.get("category", "fact")
        if content:
            try:
                mem = await store(user_id, content, category, source)
                stored.append(mem)
            except Exception:
                logger.warning("memory_store_failed", content=content[:50])

    return stored
