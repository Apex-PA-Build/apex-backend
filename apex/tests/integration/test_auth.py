import pytest
from httpx import AsyncClient


class TestAuthEndpoints:

    @pytest.mark.asyncio
    async def test_register_success(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/register", json={
            "email": "newuser@apex.ai",
            "name": "New User",
            "password": "SecurePass1",
            "timezone": "UTC",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_register_duplicate_email_returns_409(self, client: AsyncClient):
        payload = {
            "email": "duplicate@apex.ai",
            "name": "User A",
            "password": "SecurePass1",
        }
        await client.post("/api/v1/auth/register", json=payload)
        resp = await client.post("/api/v1/auth/register", json=payload)
        assert resp.status_code == 409
        assert resp.json()["error"] == "conflict"

    @pytest.mark.asyncio
    async def test_register_weak_password_returns_422(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/register", json={
            "email": "weak@apex.ai",
            "name": "User",
            "password": "weakpassword",
        })
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_login_success(self, client: AsyncClient):
        await client.post("/api/v1/auth/register", json={
            "email": "logintest@apex.ai",
            "name": "Login User",
            "password": "LoginPass1",
        })
        resp = await client.post("/api/v1/auth/login", json={
            "email": "logintest@apex.ai",
            "password": "LoginPass1",
        })
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    @pytest.mark.asyncio
    async def test_login_wrong_password_returns_401(self, client: AsyncClient):
        await client.post("/api/v1/auth/register", json={
            "email": "wrongpass@apex.ai",
            "name": "User",
            "password": "CorrectPass1",
        })
        resp = await client.post("/api/v1/auth/login", json={
            "email": "wrongpass@apex.ai",
            "password": "WrongPassword1",
        })
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_me_returns_user_info(self, client: AsyncClient, auth_headers: dict):
        resp = await client.get("/api/v1/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "id" in data
        assert "email" in data
        assert "hashed_password" not in data

    @pytest.mark.asyncio
    async def test_protected_route_without_token_returns_401(self, client: AsyncClient):
        resp = await client.get("/api/v1/auth/me")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_refresh_token(self, client: AsyncClient):
        reg = await client.post("/api/v1/auth/register", json={
            "email": "refresh@apex.ai",
            "name": "Refresh User",
            "password": "RefreshPass1",
        })
        refresh_token = reg.json()["refresh_token"]
        resp = await client.post(
            "/api/v1/auth/refresh",
            headers={"Authorization": f"Bearer {refresh_token}"},
        )
        assert resp.status_code == 200
        assert "access_token" in resp.json()
