import math
from typing import Sequence

from bench.harness.system.l2_cost import _l2_cost


def changepoints(values: Sequence[float], *, penalty: float | None = None,
                 min_size: int = 5) -> list[tuple[int, int]]:
    n = len(values)
    if n < 2 * min_size:
        return [(0, n)] if n else []
    cost = _l2_cost(values)
    if penalty is None:
        penalty = 3.0 * (cost(0, n) / n) * math.log(n)
        if penalty <= 0.0:
            return [(0, n)]

    inf = float("inf")
    f = [inf] * (n + 1)
    f[0] = -penalty
    prev = [0] * (n + 1)
    for t in range(min_size, n + 1):
        for a in range(0, t - min_size + 1):
            if f[a] == inf:
                continue
            c = f[a] + cost(a, t) + penalty
            if c < f[t]:
                f[t] = c
                prev[t] = a
    bounds: list[tuple[int, int]] = []
    t = n
    while t > 0:
        a = prev[t]
        bounds.append((a, t))
        t = a
    bounds.reverse()
    return bounds
