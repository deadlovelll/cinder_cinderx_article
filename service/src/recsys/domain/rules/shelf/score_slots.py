from recsys.domain.rules.config import SLOT_DECAY


def score_slots(bundle, freshness: int, out: list) -> int:
    weights = bundle.weights
    shares = bundle.shares
    ranks = bundle.ranks
    n = len(weights)
    n_decay = len(SLOT_DECAY)

    written = 0
    for slot in range(n):
        weight = weights[slot]
        share = shares[slot]
        rank = ranks[slot]
        base = weight * SLOT_DECAY[rank % n_decay]
        score = int(base * share) + freshness * (n - rank)
        if score <= 0:
            continue
        if written < len(out):
            out[written] = (score, slot)
        else:
            out.append((score, slot))
        written += 1
    return written
