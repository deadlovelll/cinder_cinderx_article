from recsys.domain.entities.candidate import Candidate
from recsys.domain.entities.user_context import UserContext
from recsys.domain.values.ids import ItemId


def apply_pins(chosen: list[Candidate], ctx: UserContext,
               by_id: dict[ItemId, Candidate], limit: int) -> list[Candidate]:
    if not ctx.pinned:
        return chosen

    eligible_pins = []
    for slot, iid in enumerate(ctx.pinned):
        cand = by_id.get(iid)
        if cand is not None and cand.alive:
            cand.pinned_slot = slot
            cand.reasons.append("pinned")
            eligible_pins.append(cand)

    if not eligible_pins:
        return chosen

    pinned_ids = {c.item_id for c in eligible_pins}
    rest = [c for c in chosen if c.item_id not in pinned_ids]
    return (eligible_pins + rest)[:limit]
