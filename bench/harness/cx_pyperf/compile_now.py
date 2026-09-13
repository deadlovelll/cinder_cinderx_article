from __future__ import annotations

from collections.abc import Callable
from typing import Any

from bench.harness.cx_pyperf import state
from bench.harness.cx_pyperf.jit_on import jit_on


def compile_now(*fns: Callable[..., Any], warmup: int = 0,
                run: Callable[[], Any] | None = None) -> dict[str, Any]:
    """Run `run` `warmup` times, then force_compile every fn."""
    if not jit_on():
        return {"compiled": False, "warmup": warmup}
    for _ in range(warmup):
        if run is None:
            break
        run()
    out: dict[str, Any] = {"compiled": True, "warmup": warmup, "functions": {}}
    for fn in fns:
        ok = state.jit.force_compile(fn)
        out["functions"][getattr(fn, "__qualname__", repr(fn))] = {
            "force_compile": bool(ok),
            "is_jit_compiled": bool(state.jit.is_jit_compiled(fn)),
            "interpreted_calls": state.jit.count_interpreted_calls(fn),
            "compile_time_us": state.jit.get_function_compilation_time(fn),
            "code_bytes": state.jit.get_compiled_size(fn),
        }
    return out
