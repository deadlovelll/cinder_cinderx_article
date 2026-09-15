from __future__ import annotations

import os
import platform
from typing import Any, Sequence

from bench.harness.system.constants import RESERVED_ENV
from bench.harness.system.cpu_classes import cpu_classes
from bench.harness.system.format_cpu_list import format_cpu_list
from bench.harness.system.parse_cpu_list import parse_cpu_list
from bench.harness.system.read import _read
from bench.harness.system.reserved_cpus import reserved_cpus
from bench.harness.system.shield_facts import shield_facts
from bench.harness.system.workqueue_facts import workqueue_facts


def cpu_facts(expect: Sequence[int] | None = None) -> dict[str, Any]:
    facts: dict[str, Any] = {"cpu_count": os.cpu_count()}
    if platform.system() != "Linux":
        facts["verdict"] = "unsupported"
        facts["reason"] = "CPU isolation is a Linux kernel feature"
        return facts

    isolated = parse_cpu_list(_read("/sys/devices/system/cpu/isolated"))
    nohz = parse_cpu_list(_read("/sys/devices/system/cpu/nohz_full"))
    reserved = reserved_cpus()
    facts["isolated"] = isolated
    facts["reserved"] = reserved
    facts["shield"] = shield_facts(reserved)
    facts["workqueue"] = workqueue_facts(reserved)
    facts["nohz_full"] = nohz
    facts["cmdline"] = _read("/proc/cmdline")

    try:
        facts["affinity"] = sorted(os.sched_getaffinity(0))
    except (AttributeError, OSError):
        facts["affinity"] = None

    governors, boost = {}, None
    for cpu in range(os.cpu_count() or 0):
        g = _read(f"/sys/devices/system/cpu/cpu{cpu}/cpufreq/scaling_governor")
        if g:
            governors[cpu] = g
    facts["governors"] = sorted(set(governors.values())) or None
    no_turbo = _read("/sys/devices/system/cpu/intel_pstate/no_turbo")
    if no_turbo is not None:
        boost = no_turbo == "1"
    else:
        cpufreq_boost = _read("/sys/devices/system/cpu/cpufreq/boost")
        if cpufreq_boost is not None:
            boost = cpufreq_boost == "0"
    facts["turbo_disabled"] = boost

    smt = _read("/sys/devices/system/cpu/smt/control")
    facts["smt"] = smt
    facts["scaling_driver"] = _read(
        "/sys/devices/system/cpu/cpu0/cpufreq/scaling_driver")
    classes = cpu_classes()
    facts["cpu_classes"] = {str(k): v for k, v in classes.items()} or None

    problems = []
    wanted = set(expect) if expect is not None else set(reserved)
    facts["affinity_expected"] = format_cpu_list(sorted(wanted)) if wanted else None
    notes = []
    if not reserved:
        problems.append(
            f"nothing is reserved: set {RESERVED_ENV} (and shield it) or isolcpus=")
    elif facts["affinity"] and not set(facts["affinity"]) <= wanted:
        problems.append(
            "process affinity is not confined to the reserved CPUs"
            if expect is None else
            f"process affinity is not confined to {facts['affinity_expected']}")
    if reserved and facts["shield"]["shielded"] is False:
        problems.append(
            "the reserved CPUs are not shielded: still allowed to "
            + ", ".join(facts["shield"]["leaking"]))
    if reserved and facts["workqueue"]["leaking"]:
        problems.append(
            "unbound kernel workqueues may still run on the reserved CPUs: "
            f"workqueue cpumask is {facts['workqueue']['cpus']}")
    if reserved and facts["shield"]["shielded"]:
        notes.append("user.slice is not shielded by design: nothing else should "
                     "run in this session during a campaign")
    if reserved and set(reserved) <= set(isolated):
        notes.append("reserved by isolcpus=, so the load balancer is off: "
                     "threads will not spread over this set")
    facts["notes"] = notes
    if isolated and classes:
        weights = {classes[c] for c in isolated if c in classes}
        if len(weights) > 1:
            problems.append(
                f"isolated CPUs span {len(weights)} performance classes "
                f"{sorted(weights)}: reserve one class only")
    if isolated and facts["scaling_driver"] != "intel_pstate" and not set(isolated) <= set(nohz):
        problems.append("isolated CPUs are not all in nohz_full")
    elif isolated and facts["scaling_driver"] == "intel_pstate" and set(isolated) & set(nohz):
        problems.append(
            "nohz_full covers isolated CPUs while the driver is intel_pstate: "
            "pyperf documents the pair as unstable, drop nohz_full")
    if facts["governors"] and facts["governors"] != ["performance"]:
        problems.append(f"governor is {facts['governors']}, not performance")
    if boost is False:
        problems.append("turbo is enabled")

    facts["problems"] = problems
    facts["verdict"] = "reserved" if not problems else "NOT_RESERVED"
    return facts
