import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from bench.b_border.constants import CALLS
from bench.harness import cx_pyperf as h


h.boot()


def main() -> None:
    suite = h.Suite("b_border")
    suite.parse()

    if not h.is_static():
        suite.unavailable(case="border", impl=h.config(),
                          note="needs a static config")
        suite.write_sidecar()
        return

    import bench.kernels.border_static as bs
    from _static import is_static_callable

    expected = sum(i + 1 for i in range(CALLS))

    def dynamic_loop(fn):
        def work():
            total = 0
            i = 0
            f = fn
            while i < CALLS:
                total = total + f(i)
                i = i + 1
            return total

        return work

    legs = (
        ("dynamic->untyped", dynamic_loop(bs.untyped), bs.untyped, ""),
        ("dynamic->typed", dynamic_loop(bs.typed), bs.typed, ""),
        ("static->typed", (lambda: bs.call_from_static(CALLS)), bs.call_from_static,
         "not comparable with the dynamic legs: its loop pays the static "
         "interpreter dispatch penalty measured by b_prim_op"),
    )

    jit_info: dict[str, object] = {}
    callee_static: dict[str, bool] = {}
    for impl, work, target, note in legs:
        if not suite.gate(case="border", impl=impl, got=work(), expected=expected):
            continue
        callee_static[impl] = bool(is_static_callable(target))
        if h.jit_on():
            jit_info[impl] = h.compile_now(target, warmup=1, run=work)
        suite.check_once(("border", impl), work, expected)
        suite.bench(case="border", impl=impl, fn=work, params={"calls": CALLS},
                    inner_loops=CALLS, note=note)

    suite.machine_probe()
    suite.facts["callee_is_static"] = callee_static
    suite.facts["jit"] = jit_info
    suite.write_sidecar()


if __name__ == "__main__":
    main()
