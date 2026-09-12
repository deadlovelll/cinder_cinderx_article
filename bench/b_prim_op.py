"""Cost of one primitive operation (plan 7.7)."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bench.harness import cx_pyperf as h

h.boot()

N = 500_000


def sum_plain(n: int) -> int:
    s = 0
    i = 0
    while i < n:
        s = s + i
        i = i + 1
    return s


def main() -> None:
    suite = h.Suite("b_prim_op")
    suite.parse()

    if not h.is_static():
        suite.unavailable(case="prim_op", impl=h.config(),
                          note="needs a static config; the typed leg cannot be built")
        suite.write_sidecar()
        return

    import bench.kernels.prim_static as ps

    expected = (N - 1) * N // 2
    legs = (
        ("plain/int", sum_plain),
        ("static/int", ps.sum_boxed),
        ("static/int64", ps.sum_primitive),
    )

    jit_info: dict[str, object] = {}
    for impl, fn in legs:
        work = (lambda fn=fn: fn(N))
        if not suite.gate(case="prim_op", impl=impl, got=work(), expected=expected):
            continue
        if h.jit_on():
            jit_info[impl] = h.compile_now(fn, warmup=1, run=work)
        suite.check_once(("prim_op", impl), work, expected)
        suite.bench(case="prim_op", impl=impl, fn=work,
                    params={"n": N}, inner_loops=N,
                    note="one add on the accumulator and one on the counter")

    suite.machine_probe()
    suite.facts["jit"] = jit_info
    suite.facts["jit_state"] = h.jit_snapshot()
    suite.write_sidecar()


if __name__ == "__main__":
    main()
