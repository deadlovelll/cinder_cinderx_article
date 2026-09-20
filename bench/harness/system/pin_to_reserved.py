import os
from typing import Any, Sequence

from bench.harness.system.cpu_classes import cpu_classes
from bench.harness.system.cpu_facts import cpu_facts
from bench.harness.system.parse_cpu_list import parse_cpu_list


def pin_to_reserved(cpus: Sequence[int] | None = None) -> dict[str, Any]:
    facts = cpu_facts()
    source = "argument"
    if cpus is None:
        cpus = parse_cpu_list(os.environ.get("CX_BENCH_CPUS"))
        source = "CX_BENCH_CPUS"
        if not cpus:
            cpus = facts.get("reserved") or []
            source = "reserved"
    cpus = sorted(set(cpus))
    if not cpus or not hasattr(os, "sched_setaffinity"):
        return {"pinned": False, "pin_source": None, **facts}
    classes = cpu_classes()
    weights = {classes[c] for c in cpus if c in classes}
    mixed = sorted(weights) if len(weights) > 1 else []
    if mixed and os.environ.get("CX_BENCH_ALLOW_MIXED_CLASSES") != "1":
        return {"pinned": False, "pin_source": source,
                "error": f"refusing to pin across performance classes {mixed}",
                **facts}
    try:
        os.sched_setaffinity(0, set(cpus))
    except OSError as exc:
        return {"pinned": False, "pin_source": source, "error": str(exc), **facts}
    got = sorted(os.sched_getaffinity(0))
    out = {"pinned": got == cpus, "pin_source": source, "pin_requested": cpus,
           **{**facts, "affinity": got}}
    if mixed:
        out["mixed_performance_classes"] = mixed
    return out
