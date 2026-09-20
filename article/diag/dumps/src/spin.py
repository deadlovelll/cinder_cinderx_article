from __future__ import annotations


SCALE = 16


def spin(x: int, n: int) -> int:
    total = 0
    i = 0
    while i < n:
        total = total + x * i
        i = i + 1
    return total * SCALE
