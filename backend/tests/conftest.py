import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool
from httpx import AsyncClient, ASGITransport

from app.core.database import Base, get_db
from app.core.deps import get_current_user, CurrentUser
from app.main import app

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

# StaticPool keeps a single shared connection so every session sees the same
# in-memory database; without it, pooled connections get separate empty DBs and
# tests fail non-deterministically with "no such table" depending on ordering.
engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    future=True,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def override_get_db():
    async with TestingSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


app.dependency_overrides[get_db] = override_get_db


async def override_get_current_user():
    return CurrentUser(user_id="test-user-123", email="test@dclawstack.io", role="Owner")


app.dependency_overrides[get_current_user] = override_get_current_user


@pytest_asyncio.fixture(scope="function")
async def db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with TestingSessionLocal() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def client(db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
