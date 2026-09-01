"""
The script Alembic actually runs. Two jobs: (1) tell it WHERE the database
is — reusing settings.py rather than a separate hardcoded URL, so this
never drifts from what the app itself connects to; (2) tell it WHAT the
tables should look like — by pointing it at Base.metadata from models.py.

Slightly more code than a typical Alembic env.py because our engine is
async (asyncpg) and Alembic itself is fundamentally synchronous — this file
bridges the two with asyncio.run(), a standard, documented pattern for
this exact situation, not something specific to this project.
"""

import asyncio
import os
import sys
from logging.config import fileConfig

# Alembic runs this file directly, which doesn't automatically put the
# project directory on sys.path the way running `python -m app` would —
# without this, `from app.config import settings` below fails with
# ModuleNotFoundError regardless of which directory you run `alembic` from.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.config import settings
from app.db.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# The one line that matters most: Alembic diffs the real database against
# this to figure out what CREATE/ALTER statements it needs to generate.
target_metadata = Base.metadata


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online():
    connectable = async_engine_from_config(
        {"sqlalchemy.url": settings.database_url},
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


asyncio.run(run_migrations_online())
