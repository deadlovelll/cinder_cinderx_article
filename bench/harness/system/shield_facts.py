from typing import Any, Sequence

from bench.harness.system.constants import _SHIELD_UNITS
from bench.harness.system.parse_cpu_list import parse_cpu_list
from bench.harness.system.read import _read
from bench.harness.system.reserved_cpus import reserved_cpus


def shield_facts(reserved: Sequence[int] | None = None) -> dict[str, Any]:
    reserved = list(reserved_cpus() if reserved is None else reserved)
    facts: dict[str, Any] = {"units": {}, "leaking": [], "shielded": None}
    if not reserved:
        return facts
    seen = False
    for unit in (*_SHIELD_UNITS, "user.slice"):
        eff = _read(f"/sys/fs/cgroup/{unit}/cpuset.cpus.effective")
        if eff is None:
            continue
        facts["units"][unit] = eff
        if unit not in _SHIELD_UNITS:
            continue
        seen = True
        if set(parse_cpu_list(eff)) & set(reserved):
            facts["leaking"].append(unit)
    facts["shielded"] = bool(seen and not facts["leaking"])
    return facts
