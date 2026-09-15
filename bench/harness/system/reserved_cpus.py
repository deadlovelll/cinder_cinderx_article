from __future__ import annotations

import os

from bench.harness.system.constants import RESERVED_ENV
from bench.harness.system.parse_cpu_list import parse_cpu_list
from bench.harness.system.read import _read


def reserved_cpus() -> list[int]:
    explicit = parse_cpu_list(os.environ.get(RESERVED_ENV))
    if explicit:
        return explicit
    return parse_cpu_list(_read("/sys/devices/system/cpu/isolated"))
