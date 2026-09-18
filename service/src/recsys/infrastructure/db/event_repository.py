
from __future__ import annotations

import asyncio
import logging

from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncEngine

from recsys.domain.values.ids import ItemId, UserId
from recsys.infrastructure.db.tables.impressions import impressions


class SqlEventRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._pending: set[asyncio.Task] = set()
        self._log = logging.getLogger(__name__)
        self._impr_upsert = (
            pg_insert(impressions)
            .values(user_id=bindparam("user_id"), item_id=bindparam("item_id"),
                    shown=1)
            .on_conflict_do_update(
                index_elements=[impressions.c.user_id, impressions.c.item_id],
                set_={"shown": impressions.c.shown + 1,
                      "last_shown_at": text("now()")},
            )
        )

    def schedule_impressions(self, user_id: UserId,
                             item_ids: list[ItemId]) -> None:
        if not item_ids:
            return
        task = asyncio.create_task(self.log_impressions(user_id, item_ids))
        self._pending.add(task)
        task.add_done_callback(self._pending.discard)

    async def log_impressions(self, user_id: UserId,
                              item_ids: list[ItemId]) -> None:
        if not item_ids:
            return
        params = [{"user_id": user_id, "item_id": iid} for iid in item_ids]
        try:
            async with self._engine.begin() as conn:
                await conn.execute(self._impr_upsert, params)
        except Exception:
            self._log.warning("impression write failed for user %s", user_id,
                              exc_info=True)
