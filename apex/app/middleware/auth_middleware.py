from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.core.logging import get_logger
from app.core.security import get_user_id_from_token

logger = get_logger(__name__)

PUBLIC_PATHS = {
    "/",
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/api/v1/auth/login",
    "/api/v1/auth/register",
    "/api/v1/auth/refresh",
    "/api/v1/integrations/callback/google",
    "/api/v1/integrations/callback/slack",
    "/api/v1/integrations/callback/notion",
}


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path

        # Skip auth for public paths and WebSocket upgrades (auth handled in WS handler)
        if path in PUBLIC_PATHS or request.headers.get("upgrade", "").lower() == "websocket":
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            from starlette.responses import JSONResponse
            return JSONResponse(
                status_code=401,
                content={"error": "auth_error", "message": "Missing Authorization header"},
            )

        token = auth_header.removeprefix("Bearer ").strip()
        try:
            user_id = get_user_id_from_token(token)
            request.state.user_id = user_id
        except Exception as exc:
            from starlette.responses import JSONResponse
            return JSONResponse(
                status_code=401,
                content={"error": "auth_error", "message": str(exc)},
            )

        return await call_next(request)
