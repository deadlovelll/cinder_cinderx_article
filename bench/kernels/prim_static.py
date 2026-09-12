"""Both legs of the primitive-cost comparison in one static module."""

import __static__
from __static__ import box, int64


def sum_primitive(n: int64) -> int:
    s: int64 = 0
    i: int64 = 0
    while i < n:
        s = s + i
        i = i + 1
    return box(s)


def sum_boxed(n: int) -> int:
    s: int = 0
    i: int = 0
    while i < n:
        s = s + i
        i = i + 1
    return s
