from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest


class TestMemoryService:

    @pytest.mark.asyncio
    async def test_extract_and_store_memories(self):
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()

        extracted = [
            {"content": "Prefers morning meetings", "category": "preference"},
            {"content": "Rohan owes Aryan money", "category": "relationship"},
        ]

        with patch("app.services.memory_service.extract_json", new_callable=AsyncMock) as mock_llm, \
             patch("app.services.memory_service._embed", new_callable=AsyncMock) as mock_embed, \
             patch("app.services.memory_service.upsert_memory", new_callable=AsyncMock) as mock_upsert:

            mock_llm.return_value = extracted
            mock_embed.return_value = [0.0] * 1536

            from app.services.memory_service import extract_and_store_memories
            result = await extract_and_store_memories(
                user_id=str(uuid.uuid4()),
                text="I prefer morning meetings. Rohan owes me money.",
                source="conversation",
                db=mock_db,
            )

            assert mock_llm.called
            assert mock_embed.call_count == len(extracted)
            assert mock_upsert.call_count == len(extracted)

    @pytest.mark.asyncio
    async def test_semantic_search_returns_filtered_results(self):
        raw_results = [
            {"id": "1", "score": 0.9, "payload": {"content": "Morning person", "category": "preference"}},
            {"id": "2", "score": 0.8, "payload": {"content": "Friend: Rohan", "category": "relationship"}},
        ]

        with patch("app.services.memory_service._embed", new_callable=AsyncMock) as mock_embed, \
             patch("app.services.memory_service.search_similar", new_callable=AsyncMock) as mock_search:

            mock_embed.return_value = [0.0] * 1536
            mock_search.return_value = raw_results

            from app.services.memory_service import semantic_search
            results = await semantic_search(
                user_id=str(uuid.uuid4()),
                query="morning habits",
                category="preference",
            )

            assert len(results) == 1
            assert results[0]["payload"]["category"] == "preference"

    @pytest.mark.asyncio
    async def test_extract_handles_llm_failure_gracefully(self):
        mock_db = AsyncMock()

        with patch("app.services.memory_service.extract_json", new_callable=AsyncMock) as mock_llm:
            mock_llm.side_effect = Exception("LLM timeout")

            from app.services.memory_service import extract_and_store_memories
            result = await extract_and_store_memories(
                user_id=str(uuid.uuid4()),
                text="Some conversation text.",
                source="call",
                db=mock_db,
            )

            assert result == []

    @pytest.mark.asyncio
    async def test_soft_delete_memory(self):
        mock_db = AsyncMock()
        memory_id = uuid.uuid4()
        user_id = str(uuid.uuid4())

        mock_memory = MagicMock()
        mock_memory.id = memory_id
        mock_memory.is_deleted = False

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_memory
        mock_db.execute = AsyncMock(return_value=mock_result)

        with patch("app.services.memory_service.delete_memory", new_callable=AsyncMock):
            from app.services.memory_service import soft_delete_memory
            result = await soft_delete_memory(memory_id, user_id, mock_db)

            assert result is True
            assert mock_memory.is_deleted is True
