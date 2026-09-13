from __future__ import annotations


class Cell:
    __slots__ = ("v",)

    def __init__(self, v: int) -> None:
        self.v = v

    def bump(self, d: int) -> int:
        self.v = self.v + d
        return self.v
