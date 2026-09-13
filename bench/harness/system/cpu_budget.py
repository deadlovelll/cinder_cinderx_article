from __future__ import annotations

import os
from typing import Sequence

from bench.harness.system.cpu_classes import cpu_classes
from bench.harness.system.parse_cpu_list import parse_cpu_list
from bench.harness.system.read import _read
from bench.harness.system.reserved_cpus import reserved_cpus


def cpu_budget(service: Sequence[int] | None = None) -> dict[str, list[int]]:
    """Which CPUs go to the measured service, the database, the load generator, the rest."""
    count = os.cpu_count() or 0
    if service is None:
        service = reserved_cpus()
    service = sorted(set(service))
    rest = [c for c in range(count) if c not in set(service)]
    if not service or len(rest) < 4:
        return {"service": service, "db": rest, "load": rest, "os": rest,
                "threads": rest}
    classes = cpu_classes()
    blocks: dict[int, list[int]] = {}
    for cpu in rest:
        blocks.setdefault(classes.get(cpu, 0), []).append(cpu)
    block = max(blocks.values(), key=len)
    if len(block) < 4:
        return {"service": service, "db": rest, "load": rest, "os": rest,
                "threads": rest}
    half = len(block) // 2
    load, db = block[:half], block[half:]
    leftover = [c for c in rest if c not in set(block)]
    isolated = parse_cpu_list(_read("/sys/devices/system/cpu/isolated"))
    threads = block if set(service) <= set(isolated) else service
    return {"service": service, "db": db, "load": load, "os": leftover or rest,
            "threads": threads}
