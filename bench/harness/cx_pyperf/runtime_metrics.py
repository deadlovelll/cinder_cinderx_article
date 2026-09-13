from __future__ import annotations

import sys
from typing import Any

from bench.harness.cx_pyperf.system_memory import system_memory


def runtime_metrics() -> dict[str, Any]:
    """GC, allocator and memory counters; also what the workshop sampler reads."""
    import gc
    import resource

    ru = resource.getrusage(resource.RUSAGE_SELF)
    m: dict[str, Any] = {
        "gc_stats": gc.get_stats(),
        "gc_count": list(gc.get_count()),
        "gc_freeze_count": gc.get_freeze_count(),
        "gc_threshold": list(gc.get_threshold()),
        "allocated_blocks": sys.getallocatedblocks(),
        "interned_size": sys.getunicodeinternedsize(),
        "maxrss_kb": ru.ru_maxrss // (1024 if sys.platform == "darwin" else 1),
        "minflt": ru.ru_minflt, "majflt": ru.ru_majflt,
        "nvcsw": ru.ru_nvcsw, "nivcsw": ru.ru_nivcsw,
    }
    m.update(system_memory())
    return m
