
from __future__ import annotations

from sqlalchemy import bindparam, select
from sqlalchemy.ext.asyncio import AsyncEngine

from recsys.domain.entities.item import Item
from recsys.domain.values.ids import ItemId
from recsys.infrastructure.db.mappers.item_mapper import map_items
from recsys.infrastructure.db.tables.items import items


class SqlItemRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._stmt = (
            select(
                items.c.id, items.c.category_id, items.c.brand_id,
                items.c.price_cents, items.c.margin_bps, items.c.active,
                items.c.stock, items.c.age_restricted, items.c.region_mask,
                items.c.created_at, items.c.promo_multiplier_bps,
            )
            .where(items.c.id.in_(bindparam("ids", expanding=True)))
        )

    async def get_many(self, item_ids: list[ItemId]) -> dict[ItemId, Item]:
        if not item_ids:
            return {}
        async with self._engine.connect() as conn:
            rows = (await conn.execute(self._stmt, {"ids": item_ids})).all()
        return map_items(rows)
