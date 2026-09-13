from __future__ import annotations

import os


def usable_cpu_count() -> int:
    """How many CPUs this process may run on, which is not how many the host has."""
    try:
        return len(os.sched_getaffinity(0))
    except (AttributeError, OSError):
        return os.cpu_count() or 1
