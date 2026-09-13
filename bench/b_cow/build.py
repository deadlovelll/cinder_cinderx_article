from __future__ import annotations


def build(n: int) -> list:
    """The kind of heap a preloaded application holds before it forks."""
    return [{"id": i, "name": f"item-{i}", "tags": (i % 7, i % 11)} for i in range(n)]
