from __future__ import annotations


def touch(heap: list, passes: int) -> int:
    """Read-only traversal: no mutation, only refcount traffic."""
    total = 0
    for _ in range(passes):
        for obj in heap:
            total += obj["id"] + len(obj["name"])
    return total
