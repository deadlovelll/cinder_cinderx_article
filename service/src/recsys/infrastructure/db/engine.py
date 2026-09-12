"""The async engine. Created after the fork, never before it."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from recsys.settings import Settings


def create_engine(settings: Settings) -> AsyncEngine:
    return create_async_engine(
        settings.dsn,
        pool_size=settings.db_pool_size,
        max_overflow=0,          # the pool is a fixed resource in the experiment
        pool_pre_ping=False,     # a ping per checkout would be an extra round trip
        echo=False,
    )


def driver_implementation() -> str:
    """"c" or "python": which psycopg build answered. Recorded with every result."""
    try:
        import psycopg
        import psycopg_binary  # noqa: F401

        del psycopg
        return "c"
    except ImportError:
        try:
            from psycopg import pq

            return "c" if "c" in pq.__impl__ else "python"
        except Exception:
            return "unknown"
