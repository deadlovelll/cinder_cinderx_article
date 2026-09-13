from __future__ import annotations


def reference(xs: list, ys: list, n: int):
    """Same result, separate code object, so gating leaves `accumulate` cold."""
    acc = xs[0] * 0
    for k in range(n):
        acc = acc + xs[k] * ys[k]
    return acc
