from typing import Any
from urllib.parse import urlencode

import httpx

from app.core.config import settings
from app.core.exceptions import IntegrationError, NotFoundError
from app.core.logging import get_logger
from app.core.supabase import get_client
from app.utils.encryption import decrypt, encrypt

logger = get_logger(__name__)

_OAUTH_CONFIG: dict[str, dict[str, str]] = {
    "google": {
        "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
        "redirect_uri": settings.google_redirect_uri,
        "scope": "https://www.googleapis.com/auth/calendar https://www.googleapis.com/auth/gmail.readonly",
    },
    "slack": {
        "auth_url": "https://slack.com/oauth/v2/authorize",
        "token_url": "https://slack.com/api/oauth.v2.access",
        "client_id": settings.slack_client_id,
        "client_secret": settings.slack_client_secret,
        "redirect_uri": f"http://localhost:{settings.port}/api/v1/integrations/callback/slack",
        "scope": "channels:history,channels:read,users:read",
    },
    "notion": {
        "auth_url": "https://api.notion.com/v1/oauth/authorize",
        "token_url": "https://api.notion.com/v1/oauth/token",
        "client_id": settings.notion_client_id,
        "client_secret": settings.notion_client_secret,
        "redirect_uri": f"http://localhost:{settings.port}/api/v1/integrations/callback/notion",
        "scope": "read_content",
    },
}


def get_auth_url(provider: str, user_id: str) -> str:
    cfg = _OAUTH_CONFIG.get(provider)
    if not cfg:
        raise IntegrationError(f"Unknown provider: {provider}")
    params = {
        "client_id": cfg["client_id"],
        "redirect_uri": cfg["redirect_uri"],
        "response_type": "code",
        "scope": cfg["scope"],
        "state": user_id,
        "access_type": "offline",
        "prompt": "consent",
    }
    return f"{cfg['auth_url']}?{urlencode(params)}"


async def exchange_code(provider: str, code: str, user_id: str) -> dict[str, Any]:
    cfg = _OAUTH_CONFIG.get(provider)
    if not cfg:
        raise IntegrationError(f"Unknown provider: {provider}")

    async with httpx.AsyncClient() as http:
        resp = await http.post(
            cfg["token_url"],
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": cfg["redirect_uri"],
                "client_id": cfg["client_id"],
                "client_secret": cfg["client_secret"],
            },
            headers={"Accept": "application/json"},
            timeout=15,
        )

    if resp.status_code != 200:
        raise IntegrationError(f"OAuth token exchange failed: {resp.text}")

    tokens = resp.json()
    access_token = tokens.get("access_token")
    refresh_token = tokens.get("refresh_token")
    if not access_token:
        raise IntegrationError("No access token in response")

    expires_at = None
    if tokens.get("expires_in"):
        from app.utils.datetime import utcnow
        from datetime import timedelta
        expires_at = (utcnow() + timedelta(seconds=int(tokens["expires_in"]))).isoformat()

    client = await get_client()
    payload = {
        "user_id": user_id,
        "provider": provider,
        "access_token_enc": encrypt(access_token),
        "refresh_token_enc": encrypt(refresh_token) if refresh_token else None,
        "scope": tokens.get("scope", cfg["scope"]),
        "expires_at": expires_at,
        "is_active": True,
    }
    await (
        client.table("integrations")
        .upsert(payload, on_conflict="user_id,provider")
        .execute()
    )
    logger.info("integration_connected", provider=provider, user_id=user_id)
    return {"provider": provider, "status": "connected"}


async def get_access_token(user_id: str, provider: str) -> str:
    client = await get_client()
    result = await (
        client.table("integrations")
        .select("access_token_enc, expires_at, is_active")
        .eq("user_id", user_id)
        .eq("provider", provider)
        .eq("is_active", True)
        .execute()
    )
    if not result.data:
        raise NotFoundError(f"{provider} integration")

    row = result.data[0]
    return decrypt(row["access_token_enc"])


async def list_integrations(user_id: str) -> list[dict[str, Any]]:
    client = await get_client()
    result = await (
        client.table("integrations")
        .select("provider, is_active, scope, external_user_id, expires_at, created_at")
        .eq("user_id", user_id)
        .execute()
    )
    return result.data or []


async def disconnect(user_id: str, provider: str) -> None:
    client = await get_client()
    result = await (
        client.table("integrations")
        .update({"is_active": False})
        .eq("user_id", user_id)
        .eq("provider", provider)
        .execute()
    )
    if not result.data:
        raise NotFoundError(f"{provider} integration")
