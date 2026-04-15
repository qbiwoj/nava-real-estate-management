import asyncio

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import Settings
from app.database import Base
import app.models  # noqa: F401 — registers all models with Base.metadata


@pytest.fixture(scope="session")
def test_settings():
    return Settings()


@pytest_asyncio.fixture(scope="session")
async def db_engine(test_settings):
    """One engine for the whole session. NullPool avoids loop-bound connection caching."""
    engine = create_async_engine(test_settings.TEST_DATABASE_URL, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture(scope="session")
def db_session(db_engine):
    return async_sessionmaker(db_engine, expire_on_commit=False)


@pytest.fixture
def session(db_session):
    return db_session
