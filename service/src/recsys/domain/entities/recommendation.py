from dataclasses import dataclass

from recsys.domain.values.ids import ItemId


@dataclass(slots=True, frozen=True)
class Recommendation:
    item_id: ItemId
    score: int
    rank: int
    reasons: tuple[str, ...]
