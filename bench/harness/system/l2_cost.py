from typing import Sequence


def _l2_cost(values: Sequence[float]):
    n = len(values)
    s = [0.0] * (n + 1)
    s2 = [0.0] * (n + 1)
    for i, v in enumerate(values):
        s[i + 1] = s[i] + v
        s2[i + 1] = s2[i] + v * v

    def cost(a: int, b: int) -> float:
        m = b - a
        if m <= 0:
            return 0.0
        total = s[b] - s[a]
        return max(0.0, (s2[b] - s2[a]) - total * total / m)

    return cost
