import os

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


@pytest.mark.asyncio
async def test_database_connectivity_when_configured() -> None:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("Set TEST_DATABASE_URL to run the PostgreSQL connectivity check")

    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            result = await connection.scalar(text("SELECT 1"))
        assert result == 1
    finally:
        await engine.dispose()
