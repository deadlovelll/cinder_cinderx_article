"""The static/dynamic border (plan 7.9)."""

import __static__


def typed(x: int) -> int:
    return x + 1


def untyped(x):
    return x + 1


def call_from_static(n: int) -> int:
    total: int = 0
    i: int = 0
    while i < n:
        total = total + typed(i)
        i = i + 1
    return total
