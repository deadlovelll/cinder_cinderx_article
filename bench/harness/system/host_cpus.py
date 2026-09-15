from __future__ import annotations

import os
from typing import Sequence

from bench.harness.system.format_cpu_list import format_cpu_list
from bench.harness.system.reserved_cpus import reserved_cpus


def host_cpus(exclude: Sequence[int] | None = None) -> str:
    count = os.cpu_count() or 0
    if exclude is None:
        exclude = reserved_cpus()
    keep = [c for c in range(count) if c not in set(exclude)]
    if not keep:
        raise SystemExit("every CPU is reserved: nothing is left for the host")
    return format_cpu_list(keep)
