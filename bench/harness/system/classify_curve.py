from __future__ import annotations

import math
from typing import Any, Sequence

from bench.harness.system.changepoints import changepoints
from bench.harness.system.mann_kendall import mann_kendall


def classify_curve(values: Sequence[float], *, min_size: int = 5) -> dict[str, Any]:
    """Barrett et al.'s four regimes, decided from the data rather than assumed."""
    n = len(values)
    if n < 2 * min_size:
        return {"n": n, "verdict": "too_few_samples"}

    segs = changepoints(values, min_size=min_size)
    stats = []
    for a, b in segs:
        chunk = values[a:b]
        m = sum(chunk) / len(chunk)
        var = sum((x - m) ** 2 for x in chunk) / len(chunk)
        stats.append({"start": a, "end": b, "n": b - a, "mean": m,
                      "sd": math.sqrt(var)})

    final = stats[-1]
    tol = max(final["sd"], abs(final["mean"]) * 1e-3)
    best = min(stats, key=lambda s: s["mean"])

    tail = values[final["start"]:final["end"]]
    tail_trend = mann_kendall(tail)
    half = len(tail) // 2
    if half >= 2:
        lo = sum(tail[:half]) / half
        hi = sum(tail[-half:]) / half
        tail_drift = abs(hi - lo)
        tail_settled = tail_drift <= tol
    else:
        tail_drift, tail_settled = 0.0, True

    if not tail_settled:
        verdict = "no_steady_state"
    elif len(stats) == 1:
        verdict = "flat"
    elif final["n"] < max(min_size, n // 4):
        verdict = "no_steady_state"
    elif best["mean"] < final["mean"] - tol:
        verdict = "slowdown"
    else:
        verdict = "warmup"

    return {
        "n": n, "segments": stats, "n_segments": len(stats),
        "final_mean": final["mean"], "best_mean": best["mean"],
        "best_segment_index": stats.index(best),
        "steady_from": final["start"],
        "final_over_best": (final["mean"] / best["mean"]) if best["mean"] else None,
        "tolerance": tol, "final_segment_trend": tail_trend,
        "final_segment_drift": tail_drift, "final_segment_settled": tail_settled,
        "verdict": verdict,
    }
