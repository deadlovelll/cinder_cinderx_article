
import __static__
from __static__ import box, int64


class Point:
    def __init__(self, a: int, b: int) -> None:
        self.a: int = a
        self.b: int = b


def read_attr(p: Point, n: int) -> int:
    s: int = 0
    i: int = 0
    while i < n:
        s = s + p.a
        i = i + 1
    return s


def read_two(p: Point, n: int) -> int:
    s: int = 0
    i: int = 0
    while i < n:
        s = s + p.a + p.b
        p.b = i
        i = i + 1
    return s
