from dataclasses import dataclass

from recsys.domain.entities.user import User
from recsys.domain.values.ids import ItemId


@dataclass(slots=True, frozen=True)
class UserContext:

    user: User
    recent_items: tuple[ItemId, ...]
    purchased: frozenset[ItemId]
    disliked: frozenset[ItemId]
    impressions: dict[ItemId, int]
    pinned: tuple[ItemId, ...]
