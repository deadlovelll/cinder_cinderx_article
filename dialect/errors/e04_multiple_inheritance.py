# two static bases with instance layout
import __static__

class A:
    def __init__(self) -> None:
        self.a: int = 1

class B:
    def __init__(self) -> None:
        self.b: int = 2

class C(A, B):
    pass