import platform
import sys
import sysconfig
from typing import Any

from bench.harness.cx_pyperf import state


def interp_facts() -> dict[str, Any]:
    gil = None
    if hasattr(sys, "_is_gil_enabled"):
        try:
            gil = bool(sys._is_gil_enabled())
        except Exception:
            gil = None
    facts: dict[str, Any] = {
        "executable": sys.executable,
        "version": sys.version.split()[0],
        "implementation": platform.python_implementation(),
        "compiler": platform.python_compiler(),
        "gil_enabled": gil,
        "free_threaded": bool(sysconfig.get_config_var("Py_GIL_DISABLED")),
        "config_args": sysconfig.get_config_var("CONFIG_ARGS"),
        "core_cflags": sysconfig.get_config_var("PY_CORE_CFLAGS"),
        "lazy_imports": bool(getattr(sys.flags, "lazy_imports", False)),
        "cx_config": state.config,
    }
    if state.cinderx is not None:
        from importlib.metadata import version

        try:
            facts["cinderx_version"] = version("cinderx")
        except Exception:
            facts["cinderx_version"] = "unknown"
        facts["frame_evaluator"] = state.cinderx.is_frame_evaluator_installed()
        facts["has_parallel_gc"] = state.cinderx.has_parallel_gc()
        facts["jit_enabled"] = state.jit.is_enabled()
        facts["compile_after_n_calls"] = state.jit.get_compile_after_n_calls()
    return facts
