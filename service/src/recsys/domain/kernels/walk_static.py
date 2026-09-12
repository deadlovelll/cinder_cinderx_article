"""The same two-hop walk, compiled as Static Python. Same algorithm, same results."""

import __static__
from __static__ import Array, box, int64


def from_list(src: list, n: int) -> Array[int64]:
    """The border crossing on the way in. Called at startup, never per request."""
    out = Array[int64](n)
    i: int = 0
    while i < n:
        v: int64 = int64(src[i])
        out[i] = v
        i = i + 1
    return out


def walk(
    indptr: Array[int64],
    indices: Array[int64],
    weights: Array[int64],
    seeds: Array[int64],
    n_seeds: int64,
    scores: Array[int64],
    touched: Array[int64],
) -> int64:
    n_touched: int64 = 0
    s: int64 = 0
    while s < n_seeds:
        seed: int64 = seeds[s]
        p: int64 = indptr[seed]
        pe: int64 = indptr[seed + 1]
        while p < pe:
            nb: int64 = indices[p]
            w: int64 = weights[p]
            prev: int64 = scores[nb]
            if prev == 0:
                touched[n_touched] = nb
                n_touched = n_touched + 1
            acc: int64 = prev + w * 16
            scores[nb] = acc

            q: int64 = indptr[nb]
            qe: int64 = indptr[nb + 1]
            while q < qe:
                nb2: int64 = indices[q]
                w2: int64 = weights[q]
                prev2: int64 = scores[nb2]
                if prev2 == 0:
                    touched[n_touched] = nb2
                    n_touched = n_touched + 1
                acc2: int64 = prev2 + ((w * w2 * 16) >> 6)
                scores[nb2] = acc2
                q = q + 1
            p = p + 1
        s = s + 1
    return n_touched


def take_top_ids(
    scores: Array[int64],
    touched: Array[int64],
    n_touched: int64,
    limit: int64,
    out_ids: Array[int64],
    out_scores: Array[int64],
) -> int64:
    """Top `limit` by bounded insertion into a descending Array pair."""
    n_top: int64 = 0
    floor: int64 = 0
    i: int64 = 0
    while i < n_touched:
        cand: int64 = touched[i]
        sc: int64 = scores[cand]
        i = i + 1
        if n_top == limit and sc < floor:
            continue

        lo: int64 = 0
        hi: int64 = n_top
        while lo < hi:
            mid: int64 = (lo + hi) >> 1
            ms: int64 = out_scores[mid]
            if ms > sc or (ms == sc and out_ids[mid] > cand):
                lo = mid + 1
            else:
                hi = mid
        if lo >= limit:
            continue

        j: int64 = n_top
        if n_top == limit:
            j = limit - 1
        while j > lo:
            prev_score: int64 = out_scores[j - 1]
            prev_id: int64 = out_ids[j - 1]
            out_scores[j] = prev_score
            out_ids[j] = prev_id
            j = j - 1
        out_scores[lo] = sc
        out_ids[lo] = cand
        if n_top < limit:
            n_top = n_top + 1
        if n_top == limit:
            floor = out_scores[limit - 1]
    return n_top


def reset(scores: Array[int64], touched: Array[int64], n_touched: int64) -> None:
    i: int64 = 0
    zero: int64 = 0
    while i < n_touched:
        scores[touched[i]] = zero
        i = i + 1


def boxed_pairs(out_ids: Array[int64], out_scores: Array[int64], n: int64) -> list:
    """The border crossing on the way out: the only boxing in the whole kernel."""
    res = []
    i: int64 = 0
    while i < n:
        res.append((box(out_ids[i]), box(out_scores[i])))
        i = i + 1
    return res


def select_sorted(
    scores: Array[int64],
    touched: Array[int64],
    n_touched: int64,
    limit: int64,
) -> list:
    """Top `limit` by sorting, from a static module. The fourth leg of the matrix."""
    pairs = []
    i: int64 = 0
    while i < n_touched:
        cand: int64 = touched[i]
        sc: int64 = scores[cand]
        pairs.append((box(sc), box(cand)))
        i = i + 1
    pairs.sort(reverse=True)

    out = []
    lim: int = box(limit)
    k: int = 0
    for score, cand_id in pairs:
        if k >= lim:
            break
        out.append((cand_id, score))
        k = k + 1
    return out
