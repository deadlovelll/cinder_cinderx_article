from __future__ import annotations


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
