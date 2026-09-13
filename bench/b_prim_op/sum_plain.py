from __future__ import annotations


def sum_plain(n: int) -> int:
    s = 0
    i = 0
    while i < n:
        s = s + i
        i = i + 1
    return s
