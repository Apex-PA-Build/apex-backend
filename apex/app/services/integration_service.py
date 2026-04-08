import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import IntegrationError, NotFoundError
from app.core.logging import get_logger
from app.models.integration import Integration
from app.utils.encryption import decrypt, encrypt

logger = get_logger(__name__)

OAUTH_CONFIGS: dict[str, dict] = {
    "google": {
        "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
        "redirect_uri": settings.google_redirect_uri,
        "scopes": [
            "openid", "email", "profile",
            "https://www.googleapis.com/auth/calendar",
            "https://www.googleapis.com/auth/gmail.readonly",
        ],
    },
    "slack": {
        "auth_url": "https://slack.com/oauth/v2/authorize",
        "token_url": "https://slack.com/api/oauth.v2.access",
        "client_id": settings.slack_client_id,
        "client_secret": settings.slack_client_secret,
        "redirect_uri": settings.slack_redirect_uri,
        "scopes": ["channels:history", "users:read", "chat:write"],
    },
    "notion": {
        "auth_url": "https://api.notion.com/v1/oauth/authorize",
        "token_url": "https://api.notion.com/v1/oauth/token",
        "client_id": settings.notion_client_id,
        "client_secret": settings.notion_client_secret,
        "redirect_uri": settings.notion_redirect_uri,
        "scopes": [],
    },
}


def get_auth_url(provider: str, user_id: str) -> str:
    cfg = OAUTH_CONFIGS.get(provider)
    if not cfg:
        raise IntegrationError(f"Unsupported provider: {provider}")
    params = {
        "client_id": cfg["client_id"],
        "redirect_uri": cfg["redirect_uri"],
        "response_type": "code",
        "scope": " ".join(cfg["scopes"]),
        "state": f"{user_id}:{provider}",
        "access_type": "offline",
        "prompt": "consent",
    }
    return f"{cfg['auth_url']}?{urlencode(params)}"


async def exchange_code(provider: str, code: str, user_id: str, db: AsyncSession) -> Integration:
    cfg = OAUTH_CONFIGS.get(provider)
    if not cfg:
        raise IntegrationError(f"Unsupported provider: {provider}")
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            cfg["token_url"],
            data={
                "code": code,
                "client_id": cfg["client_id"],
                "client_secret": cfg["client_secret"],
                "redirect_uri": cfg["redirect_uri"],
                "grant_type": "authorization_code",
            },
        )
    if resp.status_code != 200:
        raise IntegrationError(f"Token exchange failed: {resp.text}")
    data = resp.json()

    existing = await db.execute(
        select(Integration).where(
            Integration.user_id == uuid.UUID(user_id),
            Integration.provider == provider,
        )
    )
    integration = existing.scalar_one_or_none()
    expires_at = (
        datetime.now(timezone.utc) + timedelta(seconds=data.get("expires_in", 3600))
        if "expires_in" in data
        else None
    )
    if integration:
        integration.access_token_enc = encrypt(data["access_token"])
        if "refresh_token" in data:
            integration.refresh_token_enc = encrypt(data["refresh_token"])
        integration.expires_at = expires_at
        integration.is_active = True
    else:
        integration = Integration(
            user_id=uuid.UUID(user_id),
            provider=provider,
            access_token_enc=encrypt(data["access_token"]),
            refresh_token_enc=encrypt(data["refresh_token"]) if "refresh_token" in data else None,
            scope=data.get("scope"),
            expires_at=expires_at,
        )
        db.add(integration)
    logger.info("integration_connected", user_id=user_id, provider=provider)
    return integration


async def get_access_token(provider: str, user_id: str, db: AsyncSession) -> str:
    result = await db.execute(
        select(Integration).where(
            Integration.user_id == uuid.UUID(user_id),
            Integration.provider == provider,
            Integration.is_active == True,  # noqa: E712
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise NotFoundError(f"No active {provider} integration for user")
    return decrypt(integration.access_token_enc)


async def list_integrations(user_id: str, db: AsyncSession) -> list[Integration]:
    result = await db.execute(
        select(Integration).where(Integration.user_id == uuid.UUID(user_id))
    )
    return list(result.scalars().all())


async def disconnect(provider: str, user_id: str, db: AsyncSession) -> None:
    result = await db.execute(
        select(Integration).where(
            Integration.user_id == uuid.UUID(user_id),
            Integration.provider == provider,
        )
    )
    integration = result.scalar_one_or_none()
    if integration:
        integration.is_active = False
