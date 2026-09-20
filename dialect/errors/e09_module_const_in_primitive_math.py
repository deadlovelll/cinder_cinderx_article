# a module-level named constant used as an operand of primitive arithmetic
import __static__
from typing import Final
from __static__ import int64

SHIFT: Final[int] = 6

def f(w: int64, w2: int64) -> int64:
    acc: int64 = (w * w2) >> SHIFT
    return acc
