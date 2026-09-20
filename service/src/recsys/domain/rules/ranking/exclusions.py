from recsys.domain.entities.candidate import Candidate
from recsys.domain.entities.user_context import UserContext
from recsys.domain.rules.config import IMPRESSION_CAP


def apply_exclusions(candidates: list[Candidate], ctx: UserContext) -> None:
    purchased, disliked, impressions = ctx.purchased, ctx.disliked, ctx.impressions
    for cand in candidates:
        if not cand.alive:
            continue
        iid = cand.item_id
        if iid in purchased:
            cand.drop("already_purchased")
        elif iid in disliked:
            cand.drop("disliked")
        elif impressions.get(iid, 0) >= IMPRESSION_CAP:
            cand.drop("impression_cap")
