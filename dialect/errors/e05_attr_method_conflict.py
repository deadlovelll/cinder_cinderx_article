# an attribute and a method sharing one name, so one slot is claimed twice
import __static__

class C:
    attr: str

    def __init__(self, attr: str) -> None:
        self.attr = attr

    def attr(self) -> str:
        return self.attr
