from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient


class TestIntegrationsAPI:

    @pytest.mark.asyncio
    async def test_list_integrations_empty(self, client: AsyncClient, auth_headers: dict):
        resp = await client.get("/api/v1/integrations", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_get_google_auth_url(self, client: AsyncClient, auth_headers: dict):
        resp = await client.get(
            "/api/v1/integrations/google/auth-url", headers=auth_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "auth_url" in data
        assert "accounts.google.com" in data["auth_url"]
        assert data["provider"] == "google"

    @pytest.mark.asyncio
    async def test_unsupported_provider_returns_502(self, client: AsyncClient, auth_headers: dict):
        resp = await client.get(
            "/api/v1/integrations/twitter/auth-url", headers=auth_headers
        )
        assert resp.status_code == 502

    @pytest.mark.asyncio
    async def test_oauth_callback_exchanges_code(self, client: AsyncClient, test_user):
        mock_integration = MagicMock()
        mock_integration.id = "integration-uuid-123"

        with patch(
            "app.routers.integrations.exchange_code",
            new_callable=AsyncMock,
        ) as mock_exchange:
            mock_exchange.return_value = mock_integration
            resp = await client.get(
                "/api/v1/integrations/callback/google",
                params={"code": "mock-auth-code", "state": f"{test_user.id}:google"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["connected"] is True
        assert data["provider"] == "google"

    @pytest.mark.asyncio
    async def test_disconnect_integration(self, client: AsyncClient, auth_headers: dict):
        with patch(
            "app.routers.integrations.disconnect",
            new_callable=AsyncMock,
        ) as mock_disconnect:
            resp = await client.delete(
                "/api/v1/integrations/google",
                headers=auth_headers,
            )
        assert resp.status_code == 200
        assert resp.json()["disconnected"] is True
        assert resp.json()["provider"] == "google"
        mock_disconnect.assert_called_once()
