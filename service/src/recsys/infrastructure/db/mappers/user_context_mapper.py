from collections.abc import Sequence

from recsys.domain.entities.user import User
from recsys.domain.entities.user_context import UserContext
from recsys.domain.values.region import Region
from recsys.domain.values.segment import Segment
from recsys.infrastructure.db.mappers.id_csv import ids_from_csv


def map_user_context(row: tuple, impression_rows: Sequence[tuple],
                     pin_rows: Sequence[tuple]) -> UserContext:
    (uid, segment, region, age, basket,
     recent_raw, purchased_raw, disliked_raw) = row
    user = User(id=uid, segment=Segment(segment), region=Region(region),
                age=age, median_basket_cents=basket)
    return UserContext(
        user=user,
        recent_items=tuple(ids_from_csv(recent_raw or "")),
        purchased=frozenset(ids_from_csv(purchased_raw or "")),
        disliked=frozenset(ids_from_csv(disliked_raw or "")),
        impressions={iid: shown for iid, shown in impression_rows},
        pinned=tuple(iid for (iid,) in pin_rows),
    )
