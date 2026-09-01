"""
The actual database connection. Everything in models.py was just shapes —
this file is what turns that into something that can talk to Postgres.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

engine = create_async_engine(
    settings.database_url,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    connect_args={"timeout": settings.db_connect_timeout_s},
)

async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """A FastAPI dependency: each request that needs the database gets its
    own session, and this always closes it afterward — even if the request
    raised an error."""
    async with async_session_factory() as session:
        yield session
