from __future__ import annotations


def reference(xs: list, ys: list, n: int):
    acc = xs[0] * 0
    for k in range(n):
        acc = acc + xs[k] * ys[k]
    return acc
