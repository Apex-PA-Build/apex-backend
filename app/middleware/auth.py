import jwt
from fastapi import Request
from fastapi.responses import JSONResponse
from jwt import PyJWKClient
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.core.exceptions import AuthError

# Paths that do not require authentication
_PUBLIC_PREFIXES = (
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/api/v1/integrations/callback",
    "/api/v1/auth/register",
    "/api/v1/auth/login",
)

# JWKS client — caches public keys automatically, refreshes when a new kid appears.
# Supabase exposes its public keys at /auth/v1/.well-known/jwks.json
_jwks_client = PyJWKClient(
    f"{settings.supabase_url}/auth/v1/.well-known/jwks.json",
    cache_keys=True,
    lifespan=3600,  # refresh cached keys every hour
)


def _is_public(path: str) -> bool:
    return path == "/" or any(path.startswith(p) for p in _PUBLIC_PREFIXES)


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        if _is_public(request.url.path):
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(status_code=401, content={"detail": "Missing authorization header"})

        token = auth_header.removeprefix("Bearer ")
        try:
            signing_key = _jwks_client.get_signing_key_from_jwt(token)
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=["ES256", "HS256"],   # support both old (HS256) and new (ES256) Supabase projects
                audience="authenticated",
            )
            request.state.user_id = payload["sub"]
            request.state.user_email = payload.get("email", "")
        except jwt.ExpiredSignatureError:
            return JSONResponse(status_code=401, content={"detail": "Token expired"})
        except jwt.InvalidTokenError as e:
            return JSONResponse(status_code=401, content={"detail": f"Invalid token: {e}"})
        except Exception as e:
            return JSONResponse(status_code=401, content={"detail": f"Auth error: {e}"})

        return await call_next(request)


def get_user_id(request: Request) -> str:
    user_id: str | None = getattr(request.state, "user_id", None)
    if not user_id:
        raise AuthError()
    return user_id
