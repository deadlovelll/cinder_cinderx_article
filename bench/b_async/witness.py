from typing import Any

from bench.harness import cx_pyperf as h


def witness(work, calls: int, fns: dict[str, Any]) -> dict[str, Any]:
    jit = h.jit()
    if jit is None:
        return {}
    before = {name: jit.count_interpreted_calls(fn) for name, fn in fns.items()}
    work()
    out = {}
    for name, fn in fns.items():
        out[name] = {
            "is_jit_compiled": bool(jit.is_jit_compiled(fn)),
            "interpreted_of": calls if name != "driver" else 1,
            "interpreted_during": jit.count_interpreted_calls(fn) - before[name],
        }
    return out
