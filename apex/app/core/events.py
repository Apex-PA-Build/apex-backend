from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI

from app.core.cache import close_redis, get_redis
from app.core.logging import get_logger, setup_logging

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application startup and shutdown."""
    await _startup()
    yield
    await _shutdown()


async def _startup() -> None:
    setup_logging()
    logger.info("apex_starting")

    # Verify DB is reachable
    from app.db.session import engine
    from sqlalchemy import text

    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    logger.info("database_connected")

    # Verify Redis
    redis = await get_redis()
    await redis.ping()
    logger.info("redis_connected")

    # Ensure Qdrant collection exists
    from app.db.vector_store import ensure_collection
    try:
        await ensure_collection()
        logger.info("vector_store_ready")
    except Exception as e:
        logger.warning(f"vector_store connection skipped: {e}")

    logger.info("apex_started")


async def _shutdown() -> None:
    logger.info("apex_shutting_down")

    from app.db.session import engine
    await engine.dispose()
    logger.info("database_disconnected")

    await close_redis()
    logger.info("apex_stopped")
