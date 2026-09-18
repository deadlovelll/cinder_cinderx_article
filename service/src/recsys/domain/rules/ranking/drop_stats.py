
from __future__ import annotations

from recsys.domain.entities.candidate import Candidate


def count_drops(candidates: list[Candidate]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for cand in candidates:
        if cand.dropped_by:
            counts[cand.dropped_by] = counts.get(cand.dropped_by, 0) + 1
    return counts
