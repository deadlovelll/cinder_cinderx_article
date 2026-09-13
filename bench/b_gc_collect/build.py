from __future__ import annotations

from bench.b_gc_collect.node import Node


def build(n: int) -> list:
    """A tracked cyclic graph the collector cannot untrack away, and no garbage."""
    nodes = [Node((i, [i, i + 1])) for i in range(n)]
    for i, node in enumerate(nodes):
        node.nxt = nodes[(i + 1) % n]
        node.prev = nodes[(i - 1) % n]
    return nodes
