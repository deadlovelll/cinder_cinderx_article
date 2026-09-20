
import __static__
from __static__ import Array, box, int64

SHIFT = 12
NEG_INF = -(1 << 62)


def from_list(src: list, n: int) -> Array[int64]:
    out = Array[int64](n)
    i: int = 0
    while i < n:
        v: int64 = int64(src[i])
        out[i] = v
        i = i + 1
    return out


def zeros(n: int) -> Array[int64]:
    return Array[int64](n)


def score_all(
    flat: Array[int64],
    norms: Array[int64],
    scores: Array[int64],
    n_items: int64,
    dim: int64,
    row: int64,
) -> int64:
    neg_inf: int64 = -4611686018427387904
    zero: int64 = 0
    qbase: int64 = row * dim
    qnorm: int64 = norms[row]
    i: int64 = 0
    while i < n_items:
        if i == row:
            scores[i] = neg_inf
            i = i + 1
            continue
        base: int64 = i * dim
        acc: int64 = 0
        d: int64 = 0
        while d < dim:
            acc = acc + flat[base + d] * flat[qbase + d]
            d = d + 1
        denom: int64 = norms[i] * qnorm
        if denom == 0:
            scores[i] = zero
        else:
            num: int64 = acc * 4096
            q: int64 = num // denom
            if q * denom != num and num < 0:
                q = q - 1
            scores[i] = q
        i = i + 1
    return n_items


def take_top(
    scores: Array[int64],
    ids: Array[int64],
    n_items: int64,
    limit: int64,
    out_ids: Array[int64],
    out_scores: Array[int64],
) -> int64:
    neg_inf: int64 = -4611686018427387904
    n_out: int64 = 0
    k: int64 = 0
    while k < limit:
        best: int64 = -1
        best_score: int64 = neg_inf
        j: int64 = 0
        while j < n_items:
            s: int64 = scores[j]
            if s > best_score:
                best_score = s
                best = j
            j = j + 1
        if best < 0:
            break
        out_ids[n_out] = ids[best]
        out_scores[n_out] = best_score
        n_out = n_out + 1
        scores[best] = neg_inf
        k = k + 1
    return n_out


def boxed_pairs(out_ids: Array[int64], out_scores: Array[int64], n: int64) -> list:
    res = []
    i: int64 = 0
    while i < n:
        res.append((box(out_ids[i]), box(out_scores[i])))
        i = i + 1
    return res
