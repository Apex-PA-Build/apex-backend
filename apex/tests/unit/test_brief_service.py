from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestBriefService:
    @pytest.fixture
    def mock_user(self):
        user = MagicMock()
        user.id = "test-user-id"
        user.name = "Aryan"
        user.timezone = "Asia/Kolkata"
        user.preferences = {"work_start_hour": 9, "work_end_hour": 18, "energy_peak": "morning"}
        return user

    @pytest.mark.asyncio
    async def test_brief_generation_calls_llm(self, mock_user):
        mock_db = AsyncMock()
        narrative = "You have a productive day ahead, Aryan."

        with patch("app.services.brief_service.get_today_schedule", new_callable=AsyncMock) as mock_schedule, \
             patch("app.services.brief_service.list_tasks", new_callable=AsyncMock) as mock_tasks, \
             patch("app.services.brief_service.get_user_memories", new_callable=AsyncMock) as mock_mem, \
             patch("app.services.brief_service.get_pending_messages", new_callable=AsyncMock) as mock_agent, \
             patch("app.services.brief_service.chat", new_callable=AsyncMock) as mock_chat:

            mock_schedule.return_value = {
                "date": "2025-01-01",
                "events": [],
                "free_blocks": [],
                "total_meeting_minutes": 60,
                "deep_work_available_minutes": 180,
            }
            mock_tasks.return_value = ([], 0)
            mock_mem.return_value = []
            mock_agent.return_value = []
            mock_chat.return_value = narrative

            from app.services.brief_service import generate_daily_brief
            result = await generate_daily_brief(mock_user, mock_db)

            assert "narrative" in result
            assert "greeting" in result
            assert "Aryan" in result["greeting"]
            assert mock_chat.called

    @pytest.mark.asyncio
    async def test_brief_detects_meeting_overload(self, mock_user):
        mock_db = AsyncMock()

        with patch("app.services.brief_service.get_today_schedule", new_callable=AsyncMock) as mock_schedule, \
             patch("app.services.brief_service.list_tasks", new_callable=AsyncMock) as mock_tasks, \
             patch("app.services.brief_service.get_user_memories", new_callable=AsyncMock) as mock_mem, \
             patch("app.services.brief_service.get_pending_messages", new_callable=AsyncMock) as mock_agent, \
             patch("app.services.brief_service.chat", new_callable=AsyncMock) as mock_chat:

            mock_schedule.return_value = {
                "date": "2025-01-01",
                "events": [],
                "free_blocks": [],
                "total_meeting_minutes": 300,  # Over threshold
                "deep_work_available_minutes": 0,
            }
            mock_tasks.return_value = ([], 0)
            mock_mem.return_value = []
            mock_agent.return_value = []
            mock_chat.return_value = "Heavy meeting day."

            from app.services.brief_service import generate_daily_brief
            result = await generate_daily_brief(mock_user, mock_db)

            risks = result["risks"]
            assert any("minutes of meetings" in r["description"] for r in risks)
            assert any(r["severity"] == "high" for r in risks)

    @pytest.mark.asyncio
    async def test_brief_detects_task_overload(self, mock_user):
        mock_db = AsyncMock()
        fake_tasks = [MagicMock() for _ in range(12)]

        with patch("app.services.brief_service.get_today_schedule", new_callable=AsyncMock) as mock_schedule, \
             patch("app.services.brief_service.list_tasks", new_callable=AsyncMock) as mock_tasks, \
             patch("app.services.brief_service.get_user_memories", new_callable=AsyncMock) as mock_mem, \
             patch("app.services.brief_service.get_pending_messages", new_callable=AsyncMock) as mock_agent, \
             patch("app.services.brief_service.chat", new_callable=AsyncMock) as mock_chat:

            mock_schedule.return_value = {
                "date": "2025-01-01",
                "events": [],
                "free_blocks": [],
                "total_meeting_minutes": 60,
                "deep_work_available_minutes": 120,
            }
            mock_tasks.return_value = (fake_tasks, 12)
            mock_mem.return_value = []
            mock_agent.return_value = []
            mock_chat.return_value = "Busy day."

            from app.services.brief_service import generate_daily_brief
            result = await generate_daily_brief(mock_user, mock_db)

            risks = result["risks"]
            assert any("pending tasks" in r["description"] for r in risks)
