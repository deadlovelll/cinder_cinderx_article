from __future__ import annotations

import os

from bench.harness.system.read import _read


def cpu_classes() -> dict[int, int]:
    """Map each CPU to its performance class, so a heterogeneous set is visible."""
    out: dict[int, int] = {}
    for cpu in range(os.cpu_count() or 0):
        weight = _read(f"/sys/devices/system/cpu/cpu{cpu}/cpu_capacity")
        if weight is None:
            weight = _read(f"/sys/devices/system/cpu/cpu{cpu}/cpufreq/cpuinfo_max_freq")
        if weight is not None:
            out[cpu] = int(weight)
    return out
