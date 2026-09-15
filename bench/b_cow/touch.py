from __future__ import annotations


def touch(heap: list, passes: int) -> int:
    total = 0
    for _ in range(passes):
        for obj in heap:
            total += obj["id"] + len(obj["name"])
    return total
