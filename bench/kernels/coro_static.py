
import __static__
from __static__ import box, int64


async def spin_coro(x: int64, n: int64) -> int:
    total: int64 = 0
    i: int64 = 0
    while i < n:
        total = total + x * i
        i = i + 1
    return box(total)
