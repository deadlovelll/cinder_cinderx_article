"""Final ordering: pins in their slots, then the model's order."""

from __future__ import annotations

from recsys.domain.entities.candidate import Candidate
from recsys.domain.entities.recommendation import Recommendation


def to_recommendations(chosen: list[Candidate]) -> tuple[Recommendation, ...]:
    ordered = sorted(
        chosen,
        key=lambda c: (0, c.pinned_slot) if c.pinned_slot is not None else (1, -c.score),
    )
    return tuple(
        Recommendation(item_id=c.item_id, score=c.score, rank=rank,
                       reasons=tuple(c.reasons))
        for rank, c in enumerate(ordered)
    )
