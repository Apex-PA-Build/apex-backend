from typing import Any

from fastapi import APIRouter, Query, Request
from fastapi.responses import RedirectResponse

from app.middleware.auth import get_user_id
from app.schemas.common import MessageResponse
from app.schemas.integration import AuthURLResponse, IntegrationRead
from app.services import integration as integration_svc

router = APIRouter()


@router.get("", response_model=list[IntegrationRead])
async def list_integrations(request: Request) -> Any:
    user_id = get_user_id(request)
    return await integration_svc.list_integrations(user_id)


@router.get("/{provider}/auth-url", response_model=AuthURLResponse)
async def get_auth_url(request: Request, provider: str) -> Any:
    user_id = get_user_id(request)
    url = integration_svc.get_auth_url(provider, user_id)
    return {"url": url, "provider": provider}


@router.get("/callback/{provider}")
async def oauth_callback(
    provider: str,
    code: str = Query(...),
    state: str = Query(...),  # user_id passed via OAuth state param
) -> Any:
    """OAuth callback — no auth middleware (called by the provider)."""
    await integration_svc.exchange_code(provider, code, user_id=state)
    # Redirect to frontend success page
    return RedirectResponse(url=f"http://localhost:3000/settings?connected={provider}")


@router.delete("/{provider}", response_model=MessageResponse)
async def disconnect_integration(request: Request, provider: str) -> Any:
    user_id = get_user_id(request)
    await integration_svc.disconnect(user_id, provider)
    return {"message": f"{provider} disconnected"}
