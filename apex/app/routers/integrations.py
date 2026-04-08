from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthError
from app.db.session import get_db
from app.services.integration_service import (
    disconnect,
    exchange_code,
    get_auth_url,
    list_integrations,
)

router = APIRouter()


def _uid(request: Request) -> str:
    uid: str | None = getattr(request.state, "user_id", None)
    if not uid:
        raise AuthError("Not authenticated")
    return uid


@router.get("")
async def get_integrations(
    request: Request, db: AsyncSession = Depends(get_db)
) -> list[dict]:
    """List all connected integrations for the current user (tokens are never returned)."""
    integrations = await list_integrations(_uid(request), db)
    return [
        {
            "id": str(i.id),
            "provider": i.provider,
            "is_active": i.is_active,
            "scope": i.scope,
            "expires_at": i.expires_at.isoformat() if i.expires_at else None,
            "created_at": i.created_at.isoformat(),
        }
        for i in integrations
    ]


@router.get("/{provider}/auth-url")
async def get_oauth_url(provider: str, request: Request) -> dict:
    """Get the OAuth2 authorization URL to redirect the user to."""
    url = get_auth_url(provider, _uid(request))
    return {"auth_url": url, "provider": provider}


@router.get("/callback/{provider}")
async def oauth_callback(
    provider: str,
    code: str = Query(...),
    state: str = Query(...),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """OAuth2 callback endpoint. Exchanges code for tokens and stores them."""
    user_id = state.split(":")[0]
    integration = await exchange_code(provider, code, user_id, db)
    return {
        "connected": True,
        "provider": provider,
        "integration_id": str(integration.id),
    }


@router.delete("/{provider}", status_code=200)
async def remove_integration(
    provider: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    await disconnect(provider, _uid(request), db)
    return {"disconnected": True, "provider": provider}
