import asyncio
from functools import lru_cache

from app.core.logging import get_logger

logger = get_logger(__name__)

EMBEDDING_DIM = 384  # all-MiniLM-L6-v2 output dim


@lru_cache(maxsize=1)
def _get_model():
    from sentence_transformers import SentenceTransformer
    logger.info("loading_embedding_model", model="all-MiniLM-L6-v2")
    return SentenceTransformer("all-MiniLM-L6-v2")


async def embed_query(text: str) -> list[float]:
    loop = asyncio.get_event_loop()
    model = _get_model()
    vector = await loop.run_in_executor(None, lambda: model.encode(text, normalize_embeddings=True))
    return vector.tolist()


async def embed_documents(texts: list[str]) -> list[list[float]]:
    loop = asyncio.get_event_loop()
    model = _get_model()
    vectors = await loop.run_in_executor(None, lambda: model.encode(texts, normalize_embeddings=True))
    return [v.tolist() for v in vectors]
