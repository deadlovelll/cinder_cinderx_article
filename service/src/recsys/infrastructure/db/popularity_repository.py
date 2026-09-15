
from __future__ import annotations

from sqlalchemy import bindparam, select
from sqlalchemy.ext.asyncio import AsyncEngine

from recsys.domain.values.ids import ItemId
from recsys.infrastructure.db.tables.popularity import popularity


class SqlPopularityRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._stmt = (
            select(popularity.c.item_id, popularity.c.score)
            .order_by(popularity.c.score.desc())
            .limit(bindparam("lim"))
        )

    async def top(self, limit: int) -> list[tuple[ItemId, int]]:
        async with self._engine.connect() as conn:
            rows = (await conn.execute(self._stmt, {"lim": limit})).all()
        return [(iid, score) for iid, score in rows]
