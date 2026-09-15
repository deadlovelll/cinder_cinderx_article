
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from recsys.domain.values.ids import BrandId, CategoryId, ItemId
from recsys.domain.values.region import Region


@dataclass(slots=True, frozen=True)
class Item:

    id: ItemId
    category_id: CategoryId
    brand_id: BrandId
    price_cents: int
    margin_bps: int
    active: bool
    stock: int
    age_restricted: bool
    regions: frozenset[Region]
    created_at: datetime
    promo_multiplier_bps: int

    def is_available_in(self, region: Region) -> bool:
        return region in self.regions
