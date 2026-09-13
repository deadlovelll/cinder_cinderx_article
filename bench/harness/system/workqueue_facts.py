from __future__ import annotations

from typing import Any, Sequence

from bench.harness.system.constants import _WQ_CPUMASK
from bench.harness.system.format_cpu_list import format_cpu_list
from bench.harness.system.parse_cpu_mask import parse_cpu_mask
from bench.harness.system.read import _read
from bench.harness.system.reserved_cpus import reserved_cpus


def workqueue_facts(reserved: Sequence[int] | None = None) -> dict[str, Any]:
    """Whether unbound kernel workqueues may still run on the reserved CPUs."""
    reserved = list(reserved_cpus() if reserved is None else reserved)
    mask = _read(_WQ_CPUMASK)
    facts: dict[str, Any] = {"cpumask": mask, "cpus": None, "leaking": None}
    if mask is None or not reserved:
        return facts
    cpus = parse_cpu_mask(mask)
    facts["cpus"] = format_cpu_list(cpus)
    facts["leaking"] = bool(set(cpus) & set(reserved))
    return facts
