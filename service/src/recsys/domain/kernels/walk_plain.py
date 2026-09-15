
from __future__ import annotations

DECAY_FIRST = 16
DECAY_SECOND_SHIFT = 6


def walk(indptr, indices, weights, seeds, scores, touched) -> int:
    n_touched = 0
    for seed in seeds:
        p = indptr[seed]
        pe = indptr[seed + 1]
        while p < pe:
            nb = indices[p]
            w = weights[p]
            prev = scores[nb]
            if prev == 0:
                touched[n_touched] = nb
                n_touched += 1
            scores[nb] = prev + w * DECAY_FIRST

            q = indptr[nb]
            qe = indptr[nb + 1]
            while q < qe:
                nb2 = indices[q]
                w2 = weights[q]
                prev2 = scores[nb2]
                if prev2 == 0:
                    touched[n_touched] = nb2
                    n_touched += 1
                scores[nb2] = prev2 + (w * w2 * DECAY_FIRST >> DECAY_SECOND_SHIFT)
                q += 1
            p += 1
    return n_touched


def select_bounded(scores, touched, n_touched: int, limit: int, exclude) -> list:
    top_ids = [0] * limit
    top_scores = [0] * limit
    n_top = 0
    floor = 0

    i = 0
    while i < n_touched:
        cand = touched[i]
        sc = scores[cand]
        i += 1
        if n_top == limit and sc < floor:
            continue
        if cand in exclude:
            continue

        lo = 0
        hi = n_top
        while lo < hi:
            mid = (lo + hi) >> 1
            ms = top_scores[mid]
            if ms > sc or (ms == sc and top_ids[mid] > cand):
                lo = mid + 1
            else:
                hi = mid
        if lo >= limit:
            continue

        j = n_top if n_top < limit else limit - 1
        while j > lo:
            top_scores[j] = top_scores[j - 1]
            top_ids[j] = top_ids[j - 1]
            j -= 1
        top_scores[lo] = sc
        top_ids[lo] = cand
        if n_top < limit:
            n_top += 1
        if n_top == limit:
            floor = top_scores[limit - 1]

    return [(top_ids[j], top_scores[j]) for j in range(n_top)]


def select_sorted(scores, touched, n_touched: int, limit: int, exclude) -> list:
    pairs = []
    append = pairs.append
    i = 0
    while i < n_touched:
        cand = touched[i]
        i += 1
        if cand in exclude:
            continue
        append((scores[cand], cand))
    pairs.sort(reverse=True)
    return [(cand, score) for score, cand in pairs[:limit]]


take_top = select_sorted

SELECTIONS = {"bounded": select_bounded, "sorted": select_sorted}


def reset(scores, touched, n_touched: int) -> None:
    i = 0
    while i < n_touched:
        scores[touched[i]] = 0
        i += 1


IMPLEMENTATION = "plain"
