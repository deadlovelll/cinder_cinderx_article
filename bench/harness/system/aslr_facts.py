from __future__ import annotations

import os
from typing import Any

from bench.harness.system.aslr_empirical import _aslr_empirical
from bench.harness.system.constants import ADDR_NO_RANDOMIZE, _REEXEC_GUARD


def aslr_facts() -> dict[str, Any]:
    """What the kernel says, and what two child processes actually do."""
    facts: dict[str, Any] = {"reexec": os.environ.get(_REEXEC_GUARD, "not_attempted")}

    try:
        with open("/proc/self/personality") as fh:
            value = int(fh.read().strip(), 16)
        facts["personality"] = hex(value)
        facts["addr_no_randomize"] = bool(value & ADDR_NO_RANDOMIZE)
    except OSError:
        facts["personality"] = None
        facts["addr_no_randomize"] = None

    try:
        with open("/proc/sys/kernel/randomize_va_space") as fh:
            facts["randomize_va_space"] = int(fh.read().strip())
    except OSError:
        facts["randomize_va_space"] = None

    facts.update(_aslr_empirical())
    if facts.get("layout_stable") is True:
        facts["verdict"] = "off"
    elif facts.get("layout_stable") is False:
        facts["verdict"] = "ON"
    else:
        facts["verdict"] = "unknown"
    return facts
