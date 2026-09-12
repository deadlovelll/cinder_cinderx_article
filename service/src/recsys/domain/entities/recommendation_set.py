"""The response of one recommendation request, with its own provenance."""

from __future__ import annotations

from dataclasses import dataclass

from recsys.domain.entities.recommendation import Recommendation
from recsys.domain.values.ids import UserId


@dataclass(slots=True, frozen=True)
class RecommendationSet:
    """`dropped_by_rule` and `kernel` are carried out of the domain on purpose:"""

    user_id: UserId
    items: tuple[Recommendation, ...]
    candidates_considered: int
    dropped_by_rule: dict[str, int]
    backfilled: int
    kernel: str
