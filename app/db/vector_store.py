from typing import Any
from uuid import UUID

from qdrant_client import AsyncQdrantClient
from qdrant_client.http.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

EMBEDDING_DIM = 3072  # gemini-embedding-001
_client: AsyncQdrantClient | None = None


def get_vector_client() -> AsyncQdrantClient:
    global _client
    if _client is None:
        _client = AsyncQdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key or None,
        )
    return _client


async def ensure_collection() -> None:
    client = get_vector_client()
    collections = await client.get_collections()
    names = [c.name for c in collections.collections]
    if settings.qdrant_collection_memory not in names:
        await client.create_collection(
            collection_name=settings.qdrant_collection_memory,
            vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE),
        )
        logger.info("vector_collection_created", name=settings.qdrant_collection_memory)


async def upsert_memory(memory_id: UUID, embedding: list[float], payload: dict[str, Any]) -> None:
    client = get_vector_client()
    await client.upsert(
        collection_name=settings.qdrant_collection_memory,
        points=[PointStruct(id=str(memory_id), vector=embedding, payload=payload)],
    )


async def search_similar(
    user_id: str, embedding: list[float], limit: int = 10, score_threshold: float = 0.75
) -> list[dict[str, Any]]:
    client = get_vector_client()
    results = await client.query_points(
        collection_name=settings.qdrant_collection_memory,
        query=embedding,
        query_filter=Filter(
            must=[FieldCondition(key="user_id", match=MatchValue(value=user_id))]
        ),
        limit=limit,
        score_threshold=score_threshold,
        with_payload=True,
    )
    return [{"id": r.id, "score": r.score, "payload": r.payload} for r in results.points]


async def delete_memory(memory_id: UUID) -> None:
    client = get_vector_client()
    await client.delete(
        collection_name=settings.qdrant_collection_memory,
        points_selector=[str(memory_id)],
    )


async def delete_all_user_memories(user_id: str) -> None:
    client = get_vector_client()
    await client.delete(
        collection_name=settings.qdrant_collection_memory,
        points_selector=Filter(
            must=[FieldCondition(key="user_id", match=MatchValue(value=user_id))]
        ),
    )
    logger.info("all_user_memories_deleted", user_id=user_id)
