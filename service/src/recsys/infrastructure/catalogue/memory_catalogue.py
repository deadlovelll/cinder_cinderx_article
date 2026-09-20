from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from recsys.domain.entities.item import Item
from recsys.domain.values.ids import ItemId
from recsys.domain.values.segment import Segment
from recsys.infrastructure.db.mappers.region_mask import regions_from_mask
from recsys.infrastructure.db.tables.items import items
from recsys.infrastructure.db.tables.pins import pins
from recsys.infrastructure.db.tables.popularity import popularity


class MemoryCatalogue:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._items: dict[ItemId, Item] = {}
        self._pins: dict[Segment, tuple[ItemId, ...]] = {}
        self._popular: list[tuple[ItemId, int]] = []

    async def load(self) -> None:
        stmt = select(
            items.c.id, items.c.category_id, items.c.brand_id, items.c.price_cents,
            items.c.margin_bps, items.c.active, items.c.stock, items.c.age_restricted,
            items.c.region_mask, items.c.created_at, items.c.promo_multiplier_bps,
        )
        async with self._engine.connect() as conn:
            result = await conn.stream(stmt)
            async for (iid, cat, brand, price, margin, active, stock,
                       age_restricted, mask, created_at, promo) in result:
                self._items[iid] = Item(
                    id=iid, category_id=cat, brand_id=brand, price_cents=price,
                    margin_bps=margin, active=active, stock=stock,
                    age_restricted=age_restricted, regions=regions_from_mask(mask),
                    created_at=created_at, promo_multiplier_bps=promo,
                )

            by_segment: dict[str, list[tuple[int, ItemId]]] = {}
            for segment, slot, iid in (await conn.execute(
                    select(pins.c.segment, pins.c.slot, pins.c.item_id))).all():
                by_segment.setdefault(segment, []).append((slot, iid))
            self._pins = {
                Segment(name): tuple(iid for _, iid in sorted(rows))
                for name, rows in by_segment.items()
            }

            self._popular = [
                (iid, score) for iid, score in (await conn.execute(
                    select(popularity.c.item_id, popularity.c.score)
                    .order_by(popularity.c.score.desc()).limit(5_000))).all()
            ]

    def get_many(self, item_ids: list[ItemId]) -> dict[ItemId, Item]:
        store = self._items
        out: dict[ItemId, Item] = {}
        for iid in item_ids:
            item = store.get(iid)
            if item is not None:
                out[iid] = item
        return out

    def pins_for(self, segment: Segment) -> tuple[ItemId, ...]:
        return self._pins.get(segment, ())

    def popular(self, limit: int) -> list[tuple[ItemId, int]]:
        return self._popular[:limit]

    def size(self) -> int:
        return len(self._items)
