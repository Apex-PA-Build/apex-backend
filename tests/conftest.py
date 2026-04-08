import asyncio
from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.session import get_db

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    from main import create_app

    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


@pytest.fixture
def mock_llm():
    """Mock LLM to avoid real API calls in tests."""
    with patch("app.services.llm_service.chat", new_callable=AsyncMock) as mock:
        mock.return_value = "Mocked LLM response."
        yield mock


@pytest.fixture
def mock_redis():
    """Mock Redis cache operations."""
    with patch("app.core.cache.cache_get", new_callable=AsyncMock) as get_mock, \
         patch("app.core.cache.cache_set", new_callable=AsyncMock) as set_mock, \
         patch("app.core.cache.publish", new_callable=AsyncMock) as pub_mock:
        get_mock.return_value = None
        yield {"get": get_mock, "set": set_mock, "publish": pub_mock}


@pytest.fixture
def mock_vector_store():
    """Mock Qdrant vector store."""
    with patch("app.db.vector_store.upsert_memory", new_callable=AsyncMock) as upsert, \
         patch("app.db.vector_store.search_similar", new_callable=AsyncMock) as search, \
         patch("app.db.vector_store.delete_memory", new_callable=AsyncMock) as delete:
        search.return_value = []
        yield {"upsert": upsert, "search": search, "delete": delete}


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> Any:
    from app.core.security import hash_password
    from app.models.user import User
    import uuid

    user = User(
        id=uuid.uuid4(),
        email="test@apex.ai",
        name="Test User",
        hashed_password=hash_password("TestPass1"),
        timezone="UTC",
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def auth_headers(test_user: Any) -> dict[str, str]:
    from app.core.security import create_access_token
    token = create_access_token(str(test_user.id))
    return {"Authorization": f"Bearer {token}"}
