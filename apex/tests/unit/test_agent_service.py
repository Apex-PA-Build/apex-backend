from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest


class TestAgentService:

    @pytest.mark.asyncio
    async def test_send_message_publishes_to_redis(self):
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()

        from_user_id = str(uuid.uuid4())
        to_user_id = uuid.uuid4()

        from app.schemas.agent import AgentMessageCreate

        data = AgentMessageCreate(
            to_user_id=to_user_id,
            message_type="scheduling_request",
            content={"slots": [], "note": "Lunch?"},
        )

        with patch("app.services.agent_service.publish", new_callable=AsyncMock) as mock_publish:
            from app.services.agent_service import send_message
            msg = await send_message(from_user_id, data, mock_db)

            assert mock_publish.called
            call_args = mock_publish.call_args
            assert f"agent:{to_user_id}" in call_args[0][0]
            assert call_args[0][1]["event"] == "new_agent_message"

    @pytest.mark.asyncio
    async def test_respond_accept_sets_resolved(self):
        mock_db = AsyncMock()
        user_id = str(uuid.uuid4())
        msg_id = uuid.uuid4()

        mock_msg = MagicMock()
        mock_msg.id = msg_id
        mock_msg.to_user_id = uuid.UUID(user_id)
        mock_msg.from_user_id = uuid.uuid4()
        mock_msg.message_type = "scheduling_request"
        mock_msg.thread_id = uuid.uuid4()
        mock_msg.status = "pending"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_msg
        mock_db.execute = AsyncMock(return_value=mock_result)

        from app.schemas.agent import AgentRespondRequest

        data = AgentRespondRequest(message_id=msg_id, decision="accept")

        with patch("app.services.agent_service.publish", new_callable=AsyncMock):
            from app.services.agent_service import respond_to_message
            result = await respond_to_message(user_id, data, mock_db)

            assert result.status == "accepted"
            assert result.resolved_at is not None

    @pytest.mark.asyncio
    async def test_respond_forbidden_for_wrong_user(self):
        mock_db = AsyncMock()
        wrong_user = str(uuid.uuid4())
        correct_user = uuid.uuid4()
        msg_id = uuid.uuid4()

        mock_msg = MagicMock()
        mock_msg.id = msg_id
        mock_msg.to_user_id = correct_user  # different from wrong_user

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_msg
        mock_db.execute = AsyncMock(return_value=mock_result)

        from app.schemas.agent import AgentRespondRequest
        from app.core.exceptions import ForbiddenError

        data = AgentRespondRequest(message_id=msg_id, decision="accept")

        with pytest.raises(ForbiddenError):
            from app.services.agent_service import respond_to_message
            await respond_to_message(wrong_user, data, mock_db)

    @pytest.mark.asyncio
    async def test_counter_creates_new_message_in_thread(self):
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        user_id = str(uuid.uuid4())
        msg_id = uuid.uuid4()
        thread_id = uuid.uuid4()

        mock_msg = MagicMock()
        mock_msg.id = msg_id
        mock_msg.to_user_id = uuid.UUID(user_id)
        mock_msg.from_user_id = uuid.uuid4()
        mock_msg.message_type = "scheduling_request"
        mock_msg.thread_id = thread_id
        mock_msg.status = "pending"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_msg
        mock_db.execute = AsyncMock(return_value=mock_result)

        from app.schemas.agent import AgentRespondRequest
        data = AgentRespondRequest(
            message_id=msg_id,
            decision="counter",
            counter_content={"slots": [{"time": "Thursday 3pm"}]},
        )

        with patch("app.services.agent_service.publish", new_callable=AsyncMock):
            from app.services.agent_service import respond_to_message
            result = await respond_to_message(user_id, data, mock_db)

            assert result.status == "negotiating"
            assert mock_db.add.called  # counter message was added
