from recsys.domain.entities.candidate import Candidate
from recsys.domain.rules.config import MAX_PER_BRAND, MAX_PER_CATEGORY


def apply_diversity(candidates: list[Candidate], limit: int) -> list[Candidate]:
    per_category: dict[int, int] = {}
    per_brand: dict[int, int] = {}
    chosen: list[Candidate] = []

    for cand in sorted((c for c in candidates if c.alive),
                       key=lambda c: c.score, reverse=True):
        item = cand.item
        if item is None:
            continue
        cat, brand = item.category_id, item.brand_id
        if per_category.get(cat, 0) >= MAX_PER_CATEGORY:
            cand.drop("category_cap")
            continue
        if per_brand.get(brand, 0) >= MAX_PER_BRAND:
            cand.drop("brand_cap")
            continue
        per_category[cat] = per_category.get(cat, 0) + 1
        per_brand[brand] = per_brand.get(brand, 0) + 1
        chosen.append(cand)
        if len(chosen) >= limit:
            break
    return chosen
