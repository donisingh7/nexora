import os
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings

settings = get_settings()

# In Lambda, a frozen/thawed execution environment can outlive a pooled connection's
# validity in ways `pool_pre_ping` doesn't fully cover across cold starts, and Supabase
# (or any serverless-friendly Postgres) expects short-lived connections per invocation
# rather than a long-lived pool. Detect Lambda via its own runtime-provided env var
# (always set by the Lambda service, not something we configure) and disable pooling;
# local/dev and any long-running server process keep the default pool.
_engine_kwargs: dict = {"pool_pre_ping": True}
if os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
    _engine_kwargs = {"poolclass": NullPool}

engine = create_async_engine(settings.database_url, **_engine_kwargs)
SessionFactory = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionFactory() as session:
        yield session
