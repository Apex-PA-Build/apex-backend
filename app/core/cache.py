import json
from typing import Any

import redis.asyncio as aioredis

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_redis_client: aioredis.Redis | None = None


class MockPubSub:
    async def subscribe(self, channel):
        pass
    async def get_message(self, *args, **kwargs):
        import asyncio
        await asyncio.sleep(1)
        return None

class MockRedis:
    def __init__(self):
        self._data = {}
    async def ping(self):
        return True

    async def get(self, key):
        return self._data.get(key)
    async def setex(self, key, ttl, value):
        self._data[key] = value
    async def delete(self, *keys):
        c = 0
        for k in keys:
            if k in self._data:
                del self._data[k]
                c += 1
        return c
    async def keys(self, pattern):
        return []
    async def publish(self, channel, message):
        pass
    def pubsub(self):
        return MockPubSub()
    async def eval(self, script, numkeys, *args):
        return 1
    async def aclose(self):
        pass

_mock_redis = None

async def get_redis() -> Any:
    global _mock_redis
    if _mock_redis is None:
        _mock_redis = MockRedis()
    return _mock_redis


async def cache_get(key: str) -> Any | None:
    redis = await get_redis()
    raw = await redis.get(key)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return raw


async def cache_set(key: str, value: Any, ttl: int | None = None) -> None:
    redis = await get_redis()
    serialized = json.dumps(value) if not isinstance(value, str) else value
    if ttl is None:
        ttl = settings.redis_ttl_default
    await redis.setex(key, ttl, serialized)


async def cache_delete(key: str) -> None:
    redis = await get_redis()
    await redis.delete(key)


async def cache_delete_pattern(pattern: str) -> int:
    redis = await get_redis()
    keys = await redis.keys(pattern)
    if keys:
        return await redis.delete(*keys)
    return 0


async def publish(channel: str, message: Any) -> None:
    redis = await get_redis()
    payload = json.dumps(message) if not isinstance(message, str) else message
    await redis.publish(channel, payload)


async def subscribe(channel: str) -> aioredis.client.PubSub:
    redis = await get_redis()
    pubsub = redis.pubsub()
    await pubsub.subscribe(channel)
    return pubsub


async def close_redis() -> None:
    global _redis_client
    if _redis_client:
        await _redis_client.aclose()
        _redis_client = None
        logger.info("Redis connection closed")
