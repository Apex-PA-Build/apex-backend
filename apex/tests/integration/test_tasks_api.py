from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


class TestTasksAPI:

    @pytest.mark.asyncio
    async def test_create_task(self, client: AsyncClient, auth_headers: dict):
        resp = await client.post(
            "/api/v1/tasks",
            json={"title": "Write unit tests", "priority": "high"},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Write unit tests"
        assert data["priority"] == "high"
        assert data["status"] == "pending"

    @pytest.mark.asyncio
    async def test_list_tasks(self, client: AsyncClient, auth_headers: dict):
        await client.post("/api/v1/tasks", json={"title": "Task 1"}, headers=auth_headers)
        await client.post("/api/v1/tasks", json={"title": "Task 2"}, headers=auth_headers)
        resp = await client.get("/api/v1/tasks", headers=auth_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    @pytest.mark.asyncio
    async def test_update_task_status(self, client: AsyncClient, auth_headers: dict):
        create = await client.post(
            "/api/v1/tasks",
            json={"title": "Task to complete"},
            headers=auth_headers,
        )
        task_id = create.json()["id"]
        resp = await client.patch(
            f"/api/v1/tasks/{task_id}",
            json={"status": "done"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "done"

    @pytest.mark.asyncio
    async def test_delete_task(self, client: AsyncClient, auth_headers: dict):
        create = await client.post(
            "/api/v1/tasks",
            json={"title": "Task to delete"},
            headers=auth_headers,
        )
        task_id = create.json()["id"]
        resp = await client.delete(f"/api/v1/tasks/{task_id}", headers=auth_headers)
        assert resp.status_code == 204

    @pytest.mark.asyncio
    async def test_focus_now(self, client: AsyncClient, auth_headers: dict):
        await client.post(
            "/api/v1/tasks",
            json={"title": "Critical task", "priority": "critical"},
            headers=auth_headers,
        )
        resp = await client.get("/api/v1/tasks/focus-now", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "task" in data
        assert "reason" in data
        assert "alternatives" in data

    @pytest.mark.asyncio
    async def test_classify_tasks(self, client: AsyncClient, auth_headers: dict):
        create = await client.post(
            "/api/v1/tasks",
            json={"title": "Classify me", "priority": "high"},
            headers=auth_headers,
        )
        task_id = create.json()["id"]

        with patch("app.services.task_service.classify_single", new_callable=AsyncMock) as mock_cls:
            mock_cls.return_value = "2"
            resp = await client.post(
                "/api/v1/tasks/classify",
                json={"task_ids": [task_id]},
                headers=auth_headers,
            )
        assert resp.status_code == 200
        results = resp.json()["results"]
        assert task_id in results
        assert results[task_id] in [1, 2, 3, 4]

    @pytest.mark.asyncio
    async def test_bulk_defer(self, client: AsyncClient, auth_headers: dict):
        ids = []
        for i in range(3):
            r = await client.post("/api/v1/tasks", json={"title": f"Task {i}"}, headers=auth_headers)
            ids.append(r.json()["id"])

        resp = await client.post(
            "/api/v1/tasks/bulk-defer",
            json={"task_ids": ids, "defer_to": "2025-12-31T09:00:00Z"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["deferred"] == 3

    @pytest.mark.asyncio
    async def test_create_task_invalid_priority(self, client: AsyncClient, auth_headers: dict):
        resp = await client.post(
            "/api/v1/tasks",
            json={"title": "Bad task", "priority": "urgent"},  # invalid
            headers=auth_headers,
        )
        assert resp.status_code == 422
