from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI

from app.core.cache import close as close_redis, get_redis
from app.core.logging import get_logger
from app.core.supabase import close_client, get_client

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # ── Startup ──────────────────────────────────────────────────────
    logger.info("apex_starting")

    try:
        await get_client()
        logger.info("supabase_connected")
    except Exception as exc:
        logger.warning("supabase_unavailable", error=str(exc))

    try:
        await get_redis()
        logger.info("redis_connected")
    except Exception as exc:
        logger.warning("redis_unavailable", error=str(exc))

    try:
        from app.services.scheduler import start_scheduler
        await start_scheduler()
    except Exception as exc:
        logger.warning("scheduler_failed", error=str(exc))

    logger.info("apex_ready")
    yield

    # ── Shutdown ─────────────────────────────────────────────────────
    logger.info("apex_stopping")

    try:
        from app.services.scheduler import stop_scheduler
        await stop_scheduler()
    except Exception:
        pass

    try:
        await close_client()
    except Exception:
        pass

    try:
        await close_redis()
    except Exception:
        pass

    logger.info("apex_stopped")
