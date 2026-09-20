from recsys.domain.entities.candidate import Candidate


def apply_backfill(chosen: list[Candidate], popular: list[Candidate],
                   limit: int) -> tuple[list[Candidate], int]:
    if len(chosen) >= limit:
        return chosen, 0
    have = {c.item_id for c in chosen}
    added = 0
    for cand in popular:
        if len(chosen) >= limit:
            break
        if cand.item_id in have or not cand.alive:
            continue
        cand.reasons.append("backfill")
        chosen.append(cand)
        have.add(cand.item_id)
        added += 1
    return chosen, added
