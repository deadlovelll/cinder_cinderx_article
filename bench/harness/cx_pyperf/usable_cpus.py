from __future__ import annotations

from bench.harness import system


def usable_cpus() -> int:
    """CPUs this process may actually run on. Size thread pools with this."""
    return system.usable_cpu_count()
