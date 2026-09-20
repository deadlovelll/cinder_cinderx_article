from recsys.domain.entities.user import User
from recsys.domain.values.ids import UserId
from recsys.domain.values.region import Region
from recsys.domain.values.segment import Segment


class AnonymousContext:

    __slots__ = ("user", "recent_items", "purchased", "disliked", "impressions",
                 "pinned")

    def __init__(self, seed_item) -> None:
        region = next(iter(seed_item.regions)) if seed_item else Region.EU
        self.user = User(id=UserId(0), segment=Segment.CASUAL, region=region,
                         age=18, median_basket_cents=0)
        self.recent_items = ()
        self.purchased = frozenset()
        self.disliked = frozenset()
        self.impressions = {}
        self.pinned = ()
