# passing a primitive to a dynamic call
import __static__
from __static__ import int64

def f(n: int64) -> None:
    print(n < 0)