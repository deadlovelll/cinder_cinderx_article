
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from recsys.settings import Settings


def create_engine(settings: Settings) -> AsyncEngine:
    return create_async_engine(
        settings.dsn,
        pool_size=settings.db_pool_size,
        max_overflow=0,
        pool_pre_ping=False,
        echo=False,
    )


def driver_implementation() -> str:
    try:
        import psycopg
        import psycopg_binary

        del psycopg
        return "c"
    except ImportError:
        try:
            from psycopg import pq

            return "c" if "c" in pq.__impl__ else "python"
        except Exception:
            return "unknown"
