from __future__ import annotations

from dataclasses import dataclass

from recsys.domain.entities.recommendation import Recommendation
from recsys.domain.values.ids import ItemId


@dataclass(slots=True, frozen=True)
class SimilarResult:
    item_id: ItemId
    items: tuple[Recommendation, ...]
    candidates_considered: int
    dropped_by_rule: dict[str, int]
    implementation: str
