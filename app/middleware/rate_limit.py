from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core import cache
from app.core.config import settings


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding-window rate limiter keyed by user_id (or IP for unauthenticated)."""

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        user_id: str | None = getattr(request.state, "user_id", None)
        key = f"rl:{user_id or request.client.host}"  # type: ignore[union-attr]

        try:
            count = await cache.incr(key, ttl=settings.rate_limit_window)
            if count > settings.rate_limit_requests:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Rate limit exceeded. Try again shortly."},
                    headers={"Retry-After": str(settings.rate_limit_window)},
                )
        except Exception:
            pass  # Redis unavailable — skip rate limiting

        return await call_next(request)
