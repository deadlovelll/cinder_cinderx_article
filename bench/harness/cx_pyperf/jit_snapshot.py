from typing import Any

from bench.harness.cx_pyperf import state


def jit_snapshot() -> dict[str, Any]:
    if state.jit is None:
        return {}
    snap: dict[str, Any] = {
        "compiled_functions": len(state.jit.get_compiled_functions()),
        "compilation_time_us": state.jit.get_compilation_time(),
        "allocator": state.jit.get_allocator_stats(),
    }
    stats = state.jit.get_and_clear_runtime_stats()
    snap["deopts"] = len(stats.get("deopt", []))
    return snap
