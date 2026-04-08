import time

from fastapi import Depends, Request

from app.core.cache import get_redis
from app.core.config import settings
from app.core.exceptions import RateLimitError
from app.core.logging import get_logger

logger = get_logger(__name__)

RATE_LIMIT_SCRIPT = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local clear_before = now - window
redis.call('ZREMRANGEBYSCORE', key, 0, clear_before)
local count = redis.call('ZCARD', key)
if count >= limit then
    return 0
end
redis.call('ZADD', key, now, now .. math.random())
redis.call('EXPIRE', key, window)
return 1
"""


async def rate_limit(
    request: Request,
    limit: int = settings.rate_limit_per_minute,
    window_seconds: int = 60,
) -> None:
    user_id: str | None = getattr(request.state, "user_id", None)
    ip = request.client.host if request.client else "unknown"
    identifier = user_id or ip
    key = f"rate_limit:{identifier}:{request.url.path}"

    redis = await get_redis()
    now = time.time()
    allowed = await redis.eval(  # type: ignore[misc]
        RATE_LIMIT_SCRIPT,
        1,
        key,
        str(now),
        str(window_seconds),
        str(limit),
    )

    if not allowed:
        logger.warning("rate_limit_exceeded", identifier=identifier, path=request.url.path)
        raise RateLimitError(
            f"Rate limit exceeded: {limit} requests per {window_seconds}s"
        )


class RateLimiter:
    """Dependency factory for per-route rate limiting."""

    def __init__(self, limit: int = 60, window_seconds: int = 60) -> None:
        self.limit = limit
        self.window_seconds = window_seconds

    async def __call__(self, request: Request) -> None:
        await rate_limit(request, self.limit, self.window_seconds)
