from dataclasses import dataclass, field

from recsys.domain.entities.item import Item
from recsys.domain.values.ids import ItemId


@dataclass(slots=True)
class Candidate:

    item_id: ItemId
    affinity: int
    score: int = 0
    item: Item | None = None
    reasons: list[str] = field(default_factory=list)
    dropped_by: str | None = None
    pinned_slot: int | None = None

    def drop(self, rule: str) -> None:
        self.dropped_by = rule

    @property
    def alive(self) -> bool:
        return self.dropped_by is None
