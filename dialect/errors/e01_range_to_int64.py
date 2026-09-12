# range() yields dynamic, and dynamic -> int64 is not an allowed conversion
import __static__
from __static__ import Array, int64

def f(n: int) -> None:
    a = Array[int64](n)
    for i in range(n):
        a[i] = i
