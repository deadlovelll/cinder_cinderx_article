from __future__ import annotations

import os


ADDR_NO_RANDOMIZE = 0x0040000
_REEXEC_GUARD = "CX_BENCH_NO_ASLR"
DRIFT_MIN_EFFECT = float(os.environ.get("CX_DRIFT_MIN_EFFECT", "0.01"))
RESERVED_ENV = "CX_RESERVED_CPUS"
_SHIELD_UNITS = ("init.scope", "system.slice")
_WQ_CPUMASK = "/sys/devices/virtual/workqueue/cpumask"
