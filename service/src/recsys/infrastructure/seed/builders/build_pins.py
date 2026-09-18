from __future__ import annotations

from recsys.infrastructure.seed.config import SEGMENTS


def build_pins(n_items: int, rnd) -> list[dict]:
    return [
        {"segment": segment, "slot": slot, "item_id": next(rnd) % n_items}
        for segment in SEGMENTS
        for slot in range(3)
    ]
