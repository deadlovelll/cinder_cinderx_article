import os
from typing import Any


def jit_metrics() -> dict[str, Any]:
    try:
        import cinderx.jit as jit
    except ImportError:
        return {}
    if not jit.is_enabled():
        return {"jit_enabled": False}
    stats = jit.get_and_clear_runtime_stats()
    return {
        "jit_enabled": True,
        "jit_compiled_functions": len(jit.get_compiled_functions()),
        "jit_compilation_time_us": jit.get_compilation_time(),
        "jit_deopts": len(stats.get("deopt", [])),
        "jit_allocator": jit.get_allocator_stats(),
    }
