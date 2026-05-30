"""Singleton AsyncPostgresSaver wired to a long-lived psycopg connection pool.

Per LangGraph research (gotchas: autocommit=True, dict_row), we configure the
pool explicitly rather than using `from_conn_string` (which is a context-manager
intended for short-lived scripts).
"""

from __future__ import annotations

import asyncio
from typing import Optional

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from app.config import get_settings

_pool: Optional[AsyncConnectionPool] = None
_checkpointer: Optional[AsyncPostgresSaver] = None
_setup_lock = asyncio.Lock()


async def get_checkpointer() -> AsyncPostgresSaver:
    """Return the process-wide AsyncPostgresSaver, lazily initializing it."""
    global _pool, _checkpointer
    async with _setup_lock:
        if _checkpointer is not None:
            return _checkpointer

        settings = get_settings()
        _pool = AsyncConnectionPool(
            conninfo=settings.langgraph_database_url,
            min_size=1,
            max_size=10,
            open=False,
            kwargs={"autocommit": True, "row_factory": dict_row, "prepare_threshold": 0},
        )
        await _pool.open(wait=True)
        _checkpointer = AsyncPostgresSaver(_pool)
        await _checkpointer.setup()
        return _checkpointer


async def close_checkpointer() -> None:
    """Cleanly close the pool — call on application shutdown."""
    global _pool, _checkpointer
    if _pool is not None:
        await _pool.close()
        _pool = None
        _checkpointer = None
