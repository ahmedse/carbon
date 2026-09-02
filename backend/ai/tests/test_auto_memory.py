import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone


@pytest.mark.asyncio
async def test_feedback_message_stores_fact():
    mock_db = MagicMock()
    with patch("ai.engine.cognition.auto_memory.route_chat", new_callable=AsyncMock) as mock_route, \
         patch("ai.engine.cognition.auto_memory.LongTermMemory") as MockMem:
        mock_route.return_value = {"content": "feedback"}
        mock_store = AsyncMock()
        MockMem.return_value.store_fact = mock_store
        from ai.engine.cognition.auto_memory import AutoMemoryExtractor
        await AutoMemoryExtractor.try_extract("no that's wrong it should be metric tons", "inst1", "u1", mock_db)
        mock_store.assert_called_once()
        call_kwargs = mock_store.call_args.kwargs
        assert call_kwargs.get("memory_type") == "feedback"
        assert call_kwargs.get("category") == "feedback"


@pytest.mark.asyncio
async def test_preference_message_stores_fact():
    mock_db = MagicMock()
    with patch("ai.engine.cognition.auto_memory.route_chat", new_callable=AsyncMock) as mock_route, \
         patch("ai.engine.cognition.auto_memory.LongTermMemory") as MockMem:
        mock_route.return_value = {"content": "preference"}
        mock_store = AsyncMock()
        MockMem.return_value.store_fact = mock_store
        from ai.engine.cognition.auto_memory import AutoMemoryExtractor
        await AutoMemoryExtractor.try_extract("I always want 30-day windows not 7-day", "inst1", "u1", mock_db)
        mock_store.assert_called_once()
        assert mock_store.call_args.kwargs.get("memory_type") == "preference"


@pytest.mark.asyncio
async def test_context_message_stores_short_ttl():
    mock_db = MagicMock()
    with patch("ai.engine.cognition.auto_memory.route_chat", new_callable=AsyncMock) as mock_route, \
         patch("ai.engine.cognition.auto_memory.LongTermMemory") as MockMem:
        mock_route.return_value = {"content": "context"}
        mock_store = AsyncMock()
        MockMem.return_value.store_fact = mock_store
        from ai.engine.cognition.auto_memory import AutoMemoryExtractor
        await AutoMemoryExtractor.try_extract("I'm working on Q3 emissions reconciliation", "inst1", "u1", mock_db)
        mock_store.assert_called_once()
        kw = mock_store.call_args.kwargs
        assert kw.get("memory_type") == "context"
        # context TTL = 7 days (valid_to ~ 7 days from now)
        valid_to = kw.get("valid_to")
        assert valid_to is not None
        delta = valid_to - datetime.now(timezone.utc)
        assert 5 <= delta.days <= 8  # ±1 day tolerance


@pytest.mark.asyncio
async def test_neutral_message_no_store():
    mock_db = MagicMock()
    with patch("ai.engine.cognition.auto_memory.route_chat", new_callable=AsyncMock) as mock_route, \
         patch("ai.engine.cognition.auto_memory.LongTermMemory") as MockMem:
        mock_route.return_value = {"content": "none"}
        mock_store = AsyncMock()
        MockMem.return_value.store_fact = mock_store
        from ai.engine.cognition.auto_memory import AutoMemoryExtractor
        await AutoMemoryExtractor.try_extract("what is the platform name", "inst1", "u1", mock_db)
        mock_store.assert_not_called()


@pytest.mark.asyncio
async def test_route_chat_exception_does_not_propagate():
    mock_db = MagicMock()
    with patch("ai.engine.cognition.auto_memory.route_chat", new_callable=AsyncMock) as mock_route:
        mock_route.side_effect = RuntimeError("LLM down")
        from ai.engine.cognition.auto_memory import AutoMemoryExtractor
        # Must not raise
        await AutoMemoryExtractor.try_extract("some message", "inst1", "u1", mock_db)
