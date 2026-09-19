"""What a loop may iterate, and what the loop variable is typed as."""
import __static__
from __static__ import Array, box, clen, crange, int64


def demo() -> list:
    rows = []
    a = Array[int64](5)
    i: int64 = 0
    while i < 5:
        a[i] = i * i
        i = i + 1

    direct: int64 = 0
    for v in a:
        direct = direct + v
    rows.append(("for v in Array[int64] -- v is int64", box(direct)))

    counted: int64 = 0
    for k in crange(clen(a)):
        counted = counted + a[k]
    rows.append(("for k in crange(clen(a))", box(counted)))

    src = [1, 2, 3]
    boxed: int64 = 0
    for v2 in src:
        boxed = boxed + int64(v2)
    rows.append(("for v2 in list -- dynamic, needs int64()", box(boxed)))

    return rows
