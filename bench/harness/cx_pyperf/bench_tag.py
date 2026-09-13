from __future__ import annotations

import platform
import sys
import sysconfig

from bench.harness.cx_pyperf import state


def bench_tag() -> str:
    """Short tag identifying the running interpreter and configuration."""
    v = sys.version_info
    ft = "t" if sysconfig.get_config_var("Py_GIL_DISABLED") else ""
    impl = platform.python_implementation().lower()
    prefix = "" if impl == "cpython" else f"{impl}-"
    return f"{prefix}{v.major}{v.minor}{ft}-{state.config or 'stock'}"
