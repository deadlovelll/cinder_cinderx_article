"""A candidate travelling through the pipeline, accumulating reasons."""

from __future__ import annotations

from dataclasses import dataclass, field

from recsys.domain.entities.item import Item
from recsys.domain.values.ids import ItemId


@dataclass(slots=True)
class Candidate:
    """`dropped_by` is not decoration. A recommender that cannot say why an item"""

    item_id: ItemId
    affinity: int            # from the graph walk, fixed point
    score: int = 0           # after commercial weighting, fixed point
    item: Item | None = None
    reasons: list[str] = field(default_factory=list)
    dropped_by: str | None = None
    pinned_slot: int | None = None

    def drop(self, rule: str) -> None:
        self.dropped_by = rule

    @property
    def alive(self) -> bool:
        return self.dropped_by is None
