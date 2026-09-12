# short-circuit producing cbool on one side and bool on the other
import __static__
from __static__ import int64

def f(a: int64, b: int64, x: int, y: int) -> bool:
    return a == b or x > y
