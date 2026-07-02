"""Test fixtures.

Tests run against a real PostgreSQL (docker compose service), on a dedicated
`jewelry_test` database that is recreated around the session. Migrations and
seeds are applied for real — that *is* part of the Phase 0 exit test.
"""

import asyncio
import os

import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

TEST_DB_NAME = "jewelry_test"
ADMIN_URL = os.environ.get(
    "TEST_ADMIN_DATABASE_URL",
    "postgresql+asyncpg://jewelry:jewelry@localhost:5432/postgres",
)
TEST_URL = ADMIN_URL.rsplit("/", 1)[0] + f"/{TEST_DB_NAME}"

# Must be set before any app module reads Settings (lru_cached).
os.environ["DATABASE_URL"] = TEST_URL


async def _recreate_database() -> None:
    engine = create_async_engine(ADMIN_URL, isolation_level="AUTOCOMMIT")
    async with engine.connect() as conn:
        await conn.execute(text(f"DROP DATABASE IF EXISTS {TEST_DB_NAME} WITH (FORCE)"))
        await conn.execute(text(f"CREATE DATABASE {TEST_DB_NAME}"))
    await engine.dispose()


async def _seed() -> None:
    from app.db import dispose_engine
    from app.seeds import seed_all

    await seed_all()
    # Dispose: this ran on a temporary loop; tests get their own loops.
    await dispose_engine()


@pytest.fixture(scope="session", autouse=True)
def database():
    """Fresh test DB with real migrations + seeds applied once per session."""
    asyncio.run(_recreate_database())
    command.upgrade(Config("alembic.ini"), "head")
    asyncio.run(_seed())
    yield


@pytest.fixture(autouse=True)
async def _fresh_engine_per_loop():
    """asyncpg/redis connections are bound to an event loop; pytest-asyncio

    gives each test its own loop, so pooled clients must not outlive the test.
    """
    yield
    from app.db import dispose_engine
    from app.services.config_service import close_redis

    await close_redis()
    await dispose_engine()


@pytest.fixture
async def client():
    from app.main import app
    from app.tenancy.middleware import clear_tenant_cache

    clear_tenant_cache()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://localhost") as c:
        yield c
