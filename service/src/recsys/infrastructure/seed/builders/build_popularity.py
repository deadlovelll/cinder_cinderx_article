from __future__ import annotations


def build_popularity(n_items: int, rnd) -> list[dict]:
    return [{"item_id": i, "score": next(rnd) % 1_000_000}
            for i in range(min(n_items, 5_000))]
