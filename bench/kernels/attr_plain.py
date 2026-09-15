
from __future__ import annotations


class Point:
    def __init__(self, a: int, b: int) -> None:
        self.a = a
        self.b = b


class PointSlots:

    __slots__ = ("a", "b")

    def __init__(self, a: int, b: int) -> None:
        self.a = a
        self.b = b


def read_attr(p, n: int) -> int:
    s = 0
    i = 0
    while i < n:
        s = s + p.a
        i = i + 1
    return s


def read_two(p, n: int) -> int:
    s = 0
    i = 0
    while i < n:
        s = s + p.a + p.b
        p.b = i
        i = i + 1
    return s
