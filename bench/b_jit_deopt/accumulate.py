from __future__ import annotations


def accumulate(xs: list, ys: list, n: int):
    total = xs[0] * 0
    i = 0
    while i < n:
        total = total + xs[i] * ys[i]
        i = i + 1
    return total
