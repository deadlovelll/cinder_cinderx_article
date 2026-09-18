
from __future__ import annotations

from recsys.domain.entities.candidate import Candidate
from recsys.domain.entities.user_context import UserContext


def apply_eligibility(candidates: list[Candidate], ctx: UserContext) -> None:
    user = ctx.user
    for cand in candidates:
        item = cand.item
        if item is None:
            cand.drop("no_item_data")
            continue
        if not item.active:
            cand.drop("inactive")
        elif item.stock <= 0:
            cand.drop("out_of_stock")
        elif item.age_restricted and user.age < 18:
            cand.drop("age_restricted")
        elif not item.is_available_in(user.region):
            cand.drop("region_unavailable")
