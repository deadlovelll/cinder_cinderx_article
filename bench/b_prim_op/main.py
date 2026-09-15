from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from bench.b_prim_op.constants import N
from bench.b_prim_op.sum_plain import sum_plain
from bench.harness import cx_pyperf as h


h.boot()


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

    scale: dict[str, list] = {}
    for label, fn, extra in (("static/int64", ps.sum_primitive, ()),
                             ("static/int64-opaque", ps.sum_primitive_opaque, (7,))):
        if h.jit_on():
            h.compile_now(fn, warmup=1, run=lambda fn=fn, e=extra: fn(N, *e))
        for n in (N // 8, N // 2, N, N * 2):
            work = (lambda fn=fn, n=n, e=extra: fn(n, *e))
            work()
            b = suite.bench(case="prim_op_scale", impl=f"{label}@{n}", fn=work,
                            params={"n": n}, inner_loops=n,
                            note="per-op cost must not fall as n grows")
            if b is not None:
                scale.setdefault(label, []).append(n)
    suite.facts["scale_sweep"] = scale
    suite.facts["scale_note"] = ("a per-op cost flat across n means the loop ran; "
                                 "one falling as 1/n would mean it was folded away")

    suite.machine_probe()
    suite.facts["jit"] = jit_info
    suite.facts["jit_state"] = h.jit_snapshot()
    suite.write_sidecar()


if __name__ == "__main__":
    main()
