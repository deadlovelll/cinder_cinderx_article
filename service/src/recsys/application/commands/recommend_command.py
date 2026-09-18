from __future__ import annotations

from dataclasses import dataclass

from recsys.domain.values.ids import UserId


@dataclass(frozen=True, slots=True)
class RecommendCommand:
    user_id: UserId
    limit: int
    candidate_limit: int
