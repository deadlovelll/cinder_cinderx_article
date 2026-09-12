# overriding a method marked final
import __static__
from typing import final

class Base:
    @final
    def m(self) -> int:
        return 1

class Child(Base):
    def m(self) -> int:
        return 2
