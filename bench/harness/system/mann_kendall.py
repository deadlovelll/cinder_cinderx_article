import math
from typing import Any, Sequence

from bench.harness.system.constants import DRIFT_MIN_EFFECT
from bench.harness.system.normal_cdf import _normal_cdf


def mann_kendall(values: Sequence[float],
                 min_effect: float | None = None) -> dict[str, Any]:
    n = len(values)
    if n < 8:
        return {"n": n, "verdict": "too_few_samples"}

    s = 0
    slopes = []
    for i in range(n - 1):
        vi = values[i]
        for j in range(i + 1, n):
            d = values[j] - vi
            s += (d > 0) - (d < 0)
            slopes.append(d / (j - i))

    var = n * (n - 1) * (2 * n + 5) / 18.0
    if s > 0:
        z = (s - 1) / math.sqrt(var)
    elif s < 0:
        z = (s + 1) / math.sqrt(var)
    else:
        z = 0.0
    p = 2.0 * (1.0 - _normal_cdf(abs(z)))

    slopes.sort()
    mid = len(slopes) // 2
    slope = slopes[mid] if len(slopes) % 2 else (slopes[mid - 1] + slopes[mid]) / 2.0

    first = values[: n // 2]
    second = values[-(n // 2):]
    half_ratio = (sum(second) / len(second)) / (sum(first) / len(first))

    floor = DRIFT_MIN_EFFECT if min_effect is None else min_effect
    effect = half_ratio - 1.0
    agree = (s > 0) == (effect > 0)
    if p >= 0.05 or abs(effect) < floor or not agree:
        verdict = "no_trend"
    elif s > 0:
        verdict = "SLOWING"
    else:
        verdict = "speeding_up"

    return {
        "n": n, "S": s, "z": round(z, 3), "p": round(p, 5),
        "slope_per_sample": slope, "second_half_over_first": round(half_ratio, 4),
        "effect": round(effect, 5), "min_effect": floor, "direction_agrees": agree,
        "verdict": verdict,
    }
