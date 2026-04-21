import json
from typing import Any

from redis.asyncio import Redis, from_url

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_redis: Redis | None = None  # type: ignore[type-arg]


async def get_redis() -> Redis:  # type: ignore[type-arg]
    global _redis
    if _redis is None:
        _redis = from_url(settings.redis_url, decode_responses=True)
        logger.info("redis_connected", url=settings.redis_url)
    return _redis


async def get(key: str) -> Any | None:
    r = await get_redis()
    val = await r.get(key)
    return json.loads(val) if val is not None else None


async def set(key: str, value: Any, ttl: int = 3600) -> None:
    r = await get_redis()
    await r.setex(key, ttl, json.dumps(value, default=str))


async def delete(key: str) -> None:
    r = await get_redis()
    await r.delete(key)


async def incr(key: str, ttl: int = 60) -> int:
    r = await get_redis()
    pipe = r.pipeline()
    await pipe.incr(key)
    await pipe.expire(key, ttl)
    results = await pipe.execute()
    return int(results[0])


async def publish(channel: str, message: dict[str, Any]) -> None:
    r = await get_redis()
    await r.publish(channel, json.dumps(message, default=str))


async def close() -> None:
    global _redis
    if _redis:
        await _redis.aclose()
        _redis = None
    logger.info("redis_disconnected")
