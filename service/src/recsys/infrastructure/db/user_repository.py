
from __future__ import annotations

from sqlalchemy import bindparam, select
from sqlalchemy.ext.asyncio import AsyncEngine

from recsys.domain.entities.user import User
from recsys.domain.entities.user_context import UserContext
from recsys.domain.values.ids import UserId
from recsys.domain.values.region import Region
from recsys.domain.values.segment import Segment
from recsys.infrastructure.db.mappers.id_csv import ids_from_csv
from recsys.infrastructure.db.tables.impressions import impressions
from recsys.infrastructure.db.tables.user_state import user_state
from recsys.infrastructure.db.tables.users import users


class SqlUserRepository:
    def __init__(self, engine: AsyncEngine, catalogue) -> None:
        self._engine = engine
        self._catalogue = catalogue
        self._user_stmt = (
            select(users.c.id, users.c.segment, users.c.region, users.c.age,
                   users.c.median_basket_cents,
                   user_state.c.recent_items, user_state.c.purchased_items,
                   user_state.c.disliked_items)
            .join(user_state, user_state.c.user_id == users.c.id, isouter=True)
            .where(users.c.id == bindparam("uid"))
        )
        self._impr_stmt = (
            select(impressions.c.item_id, impressions.c.shown)
            .where(impressions.c.user_id == bindparam("uid"))
        )

    async def load_context(self, user_id: UserId) -> UserContext | None:
        async with self._engine.connect() as conn:
            row = (await conn.execute(self._user_stmt, {"uid": user_id})).first()
            if row is None:
                return None
            impr = (await conn.execute(self._impr_stmt, {"uid": user_id})).all()

        (uid, segment, region, age, basket,
         recent_raw, purchased_raw, disliked_raw) = row
        seg = Segment(segment)
        user = User(id=uid, segment=seg, region=Region(region), age=age,
                    median_basket_cents=basket)
        return UserContext(
            user=user,
            recent_items=tuple(ids_from_csv(recent_raw or "")),
            purchased=frozenset(ids_from_csv(purchased_raw or "")),
            disliked=frozenset(ids_from_csv(disliked_raw or "")),
            impressions={iid: shown for iid, shown in impr},
            pinned=self._catalogue.pins_for(seg),
        )
