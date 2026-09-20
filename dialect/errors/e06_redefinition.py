# the same name annotated in both arms of a branch
import __static__

def f(flag: bool) -> int:
    if flag:
        x: int = 1
    else:
        x: int = 2
    return x