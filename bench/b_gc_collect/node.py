from __future__ import annotations


class Node:
    __slots__ = ("nxt", "prev", "payload")

    def __init__(self, payload) -> None:
        self.nxt = None
        self.prev = None
        self.payload = payload
