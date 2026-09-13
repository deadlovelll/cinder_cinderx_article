from __future__ import annotations


def hot_attr(cells: list, rounds: int) -> int:
    for c in cells:
        c.v = 0
    total = 0
    for _ in range(rounds):
        for c in cells:
            total += c.bump(1)
    return total
