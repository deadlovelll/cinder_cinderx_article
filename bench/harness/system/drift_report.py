from __future__ import annotations

from typing import Any, Sequence

from bench.harness.system.constants import DRIFT_MIN_EFFECT
from bench.harness.system.mann_kendall import mann_kendall


def drift_report(named_values: dict[str, Sequence[float]]) -> dict[str, Any]:
    """Run the trend test over every benchmark's samples in temporal order."""
    per_bench = {name: mann_kendall(vals) for name, vals in named_values.items()}
    slowing = sorted(n for n, r in per_bench.items() if r.get("verdict") == "SLOWING")
    return {
        "test": "mann_kendall",
        "alpha": 0.05,
        "min_effect": DRIFT_MIN_EFFECT,
        "benchmarks": per_bench,
        "slowing": slowing,
        "verdict": "DRIFT" if slowing else "ok",
    }
