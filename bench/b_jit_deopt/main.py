from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from bench.b_jit_deopt.accumulate import accumulate
from bench.b_jit_deopt.constants import N
from bench.b_jit_deopt.reference import reference
from bench.harness import cx_pyperf as h


h.boot()


def main() -> None:
    suite = h.Suite("b_jit_deopt")
    suite.parse()

    if not h.jit_on():
        suite.unavailable(case="jit_deopt", impl="all", note="needs a JIT config")
        suite.write_sidecar()
        return

    ints = [i % 97 for i in range(N)]
    floats = [float(i % 97) for i in range(N)]
    decs = [Decimal(i % 97) for i in range(N)]
    shapes = (("mono", ints, ints), ("mixed", ints, floats), ("poly", ints, decs))

    mono_work = lambda: accumulate(ints, ints, N)
    info = h.compile_now(accumulate, warmup=1, run=mono_work)
    h.jit().get_and_clear_runtime_stats()

    deopts: dict[str, object] = {}
    for name, xs, ys in shapes:
        work = (lambda xs=xs, ys=ys: accumulate(xs, ys, N))
        expected = reference(xs, ys, N)
        if not suite.gate(case="jit_deopt", impl=name, got=work(), expected=expected,
                          tol=1e-12):
            continue
        stats = h.jit().get_and_clear_runtime_stats()
        deopts[name] = {
            "events_on_first_calls": len(stats.get("deopt", [])),
            "detail": stats.get("deopt", [])[:5],
            "still_compiled": bool(h.jit().is_jit_compiled(accumulate)),
        }
        suite.check_once(("jit_deopt", name), work, expected, tol=1e-12)
        suite.bench(case="jit_deopt", impl=name, fn=work, params={"n": N},
                    inner_loops=N, note=f"compiled on mono; running {name}")

    suite.machine_probe()
    suite.facts["compiled_on"] = "mono"
    suite.facts["jit"] = info
    suite.facts["deopts"] = deopts
    suite.write_sidecar()


if __name__ == "__main__":
    main()
