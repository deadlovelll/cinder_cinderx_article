from collections.abc import Sequence

from recsys.domain.entities.item import Item
from recsys.domain.values.ids import ItemId
from recsys.infrastructure.db.mappers.region_mask import regions_from_mask


def map_items(rows: Sequence[tuple]) -> dict[ItemId, Item]:
    out: dict[ItemId, Item] = {}
    for (iid, cat, brand, price, margin, active, stock, age_restricted,
         mask, created_at, promo) in rows:
        out[iid] = Item(
            id=iid, category_id=cat, brand_id=brand, price_cents=price,
            margin_bps=margin, active=active, stock=stock,
            age_restricted=age_restricted, regions=regions_from_mask(mask),
            created_at=created_at, promo_multiplier_bps=promo,
        )
    return out
