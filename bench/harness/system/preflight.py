from __future__ import annotations

from typing import Any, Sequence

from bench.harness.system.aslr_facts import aslr_facts
from bench.harness.system.cpu_facts import cpu_facts


def preflight(*, strict: bool = False,
              expect: Sequence[int] | None = None) -> dict[str, Any]:
    """Gather all preconditions. With strict=True, refuse to run a bad host."""
    facts = {"aslr": aslr_facts(), "cpu": cpu_facts(expect)}
    bad = [
        f"aslr={facts['aslr']['verdict']}" if facts["aslr"]["verdict"] != "off" else None,
        f"cpu={facts['cpu']['verdict']}" if facts["cpu"]["verdict"] != "reserved" else None,
    ]
    facts["problems"] = [b for b in bad if b]
    facts["verdict"] = "ok" if not facts["problems"] else "DEGRADED"
    if strict and facts["problems"]:
        raise SystemExit(
            "refusing to measure on this host: " + ", ".join(facts["problems"])
            + "\nsee bench/harness/system and "
              "https://pyperf.readthedocs.io/en/latest/system.html"
        )
    return facts
