import os
from typing import Sequence

from bench.harness.system.reserved_cpus import reserved_cpus


def irq_mask(exclude: Sequence[int] | None = None) -> str:
    count = os.cpu_count() or 0
    if exclude is None:
        exclude = reserved_cpus()
    keep = [c for c in range(count) if c not in set(exclude)]
    if not keep:
        raise SystemExit("every CPU is reserved: no CPU left to take interrupts")
    bits = sum(1 << c for c in keep)
    groups = max(1, (count + 31) // 32)
    return ",".join(f"{(bits >> (32 * g)) & 0xFFFFFFFF:08x}"
                    for g in reversed(range(groups)))
