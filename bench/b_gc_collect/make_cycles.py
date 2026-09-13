from __future__ import annotations


def make_cycles(n: int) -> list:
    """n objects in cyclic pairs: only the collector can reclaim them."""
    out = []
    for _ in range(n // 2):
        a: dict = {}
        b: dict = {"peer": a}
        a["peer"] = b
        out.append(a)
    return out
