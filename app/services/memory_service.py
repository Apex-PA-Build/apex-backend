import uuid
from typing import Any

import anthropic
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.db.vector_store import (
    delete_all_user_memories,
    delete_memory,
    search_similar,
    upsert_memory,
)
from app.models.memory import Memory
from app.services.llm_service import extract_json

logger = get_logger(__name__)


import google.generativeai as genai

async def _embed(text: str) -> list[float]:
    """Generate an embedding using Gemini text-embedding-004."""
    try:
        genai.configure(api_key=settings.gemini_api_key)
        result = genai.embed_content(
            model="models/gemini-embedding-001",
            content=text,
            task_type="retrieval_document",
        )
        return result['embedding']
    except Exception as e:
        logger.error(f"Gemini Embedding failed (Likely invalid/expired key): {e}")
        # Return empty vector to prevent entire background flow from crashing
        # Assuming Qdrant vector size 768.
        return [0.0] * 768


async def extract_and_store_memories(
    user_id: str,
    text: str,
    source: str,
    db: AsyncSession,
) -> list[Memory]:
    """Extract memorable facts from text and store them in DB + vector store."""
    prompt = f"""Extract memorable personal facts, preferences, commitments, and relationship context from this text.
Return a JSON list of objects, each with: content (string), category (preference|relationship|pattern|fact|decision|commitment).
Only include genuinely useful long-term memories, not transient details.

Text: {text[:4000]}"""

    try:
        items: list[dict[str, Any]] = await extract_json(prompt)  # type: ignore[assignment]
    except Exception as exc:
        logger.warning("memory_extraction_failed", error=str(exc))
        return []

    stored: list[Memory] = []
    for item in items[:20]:  # cap per call
        content = item.get("content", "").strip()
        category = item.get("category", "fact")
        if not content:
            continue

        memory = Memory(
            user_id=uuid.UUID(user_id),
            content=content,
            category=category,
            source=source,
        )
        db.add(memory)
        await db.flush()

        embedding = await _embed(content)
        await upsert_memory(
            memory_id=memory.id,
            embedding=embedding,
            payload={"user_id": user_id, "content": content, "category": category},
        )
        memory.embedding_id = str(memory.id)
        stored.append(memory)

    logger.info("memories_stored", user_id=user_id, count=len(stored), source=source)
    return stored


async def semantic_search(
    user_id: str,
    query: str,
    limit: int = 10,
    category: str | None = None,
    db: AsyncSession | None = None,
) -> list[dict[str, Any]]:
    embedding = await _embed(query)
    results = await search_similar(user_id, embedding, limit=limit)
    if category:
        results = [r for r in results if r["payload"].get("category") == category]
    return results


async def get_user_memories(
    user_id: str,
    db: AsyncSession,
    limit: int = 50,
) -> list[Memory]:
    result = await db.execute(
        select(Memory)
        .where(Memory.user_id == uuid.UUID(user_id), Memory.is_deleted == False)  # noqa: E712
        .order_by(Memory.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def soft_delete_memory(memory_id: uuid.UUID, user_id: str, db: AsyncSession) -> bool:
    result = await db.execute(
        select(Memory).where(Memory.id == memory_id, Memory.user_id == uuid.UUID(user_id))
    )
    memory = result.scalar_one_or_none()
    if not memory:
        return False
    memory.is_deleted = True
    await delete_memory(memory_id)
    return True


async def delete_all_memories(user_id: str, db: AsyncSession) -> int:
    memories = await get_user_memories(user_id, db, limit=10000)
    for m in memories:
        m.is_deleted = True
    await delete_all_user_memories(user_id)
    return len(memories)
