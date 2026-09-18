from __future__ import annotations

from datetime import timedelta

from recsys.infrastructure.seed.config import (
    BASE_DATE, N_BRANDS, N_CATEGORIES, REGION_MASKS,
)


def build_items(n_items: int, rnd) -> list[dict]:
    out = []
    for i in range(n_items):
        showable = next(rnd) % 100
        inactive = showable < 5
        out_of_stock = 5 <= showable < 10
        promoted = next(rnd) % 50 == 0
        out.append({
            "id": i,
            "category_id": next(rnd) % N_CATEGORIES,
            "brand_id": next(rnd) % N_BRANDS,
            "price_cents": 500 + next(rnd) % 200_000,
            "margin_bps": 200 + next(rnd) % 4_000,
            "active": not inactive,
            "stock": 0 if out_of_stock else 1 + next(rnd) % 50,
            "age_restricted": next(rnd) % 1000 < 30,
            "region_mask": REGION_MASKS[next(rnd) % len(REGION_MASKS)],
            "created_at": BASE_DATE - timedelta(days=next(rnd) % 400),
            "promo_multiplier_bps": (10_000 + next(rnd) % 8_000) if promoted else 10_000,
        })
    return out
