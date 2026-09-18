from __future__ import annotations


def take_top_slots(scored: list, written: int, limit: int) -> list:
    top = sorted(scored[:written], reverse=True)
    if limit < len(top):
        return top[:limit]
    return top
