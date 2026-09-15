from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from bench.b_jit_warmup.cell import Cell
from bench.b_jit_warmup.constants import N_ITEMS, ROUNDS
from bench.b_jit_warmup.hot_attr import hot_attr
from bench.b_jit_warmup.hot_index import hot_index
from bench.harness import cx_pyperf as h


h.boot()


def main() -> None:
    suite = h.Suite("b_jit_warmup", forward=("warmup-calls", "shape"))
    suite.runner.argparser.add_argument("--warmup-calls", type=int, default=0,
                                        help="calls before force_compile, per process")
    suite.runner.argparser.add_argument("--shape", choices=("attr", "index"),
                                        default="attr")
    args = suite.parse()
    warmup, shape = args.warmup_calls, args.shape

    if not h.jit_on():
        suite.unavailable(case="jit_warmup", impl=f"{shape}/w{warmup}",
                          note="needs a JIT config")
        suite.write_sidecar()
        return

    n = N_ITEMS
    if shape == "attr":
        cells = [Cell(i) for i in range(n)]
        hot, work = hot_attr, (lambda: hot_attr(cells, ROUNDS))
        expected = n * ROUNDS * (ROUNDS + 1) // 2
    else:
        buf = [i * 3 % 101 for i in range(n)]
        hot, work = hot_index, (lambda: hot_index(buf, ROUNDS))
        s = sum(buf[i] * buf[n - 1 - i] for i in range(n))
        expected = ROUNDS * s + n * ROUNDS * (ROUNDS - 1) // 2

    for _ in range(warmup):
        work()
    before = h.jit().count_interpreted_calls(hot)
    info = h.compile_now(hot, warmup=0)

    suite.check_once(("jit_warmup", shape), work, expected)
    suite.bench(case="jit_warmup", impl=f"{shape}/w{warmup}", fn=work,
                params={"items": N_ITEMS, "rounds": ROUNDS,
                        "warmup_calls": warmup, "shape": shape},
                note=f"compiled after {before} interpreted calls")

    suite.machine_probe()
    suite.facts["warmup_calls_requested"] = warmup
    suite.facts["interpreted_calls_before_compile"] = before
    suite.facts["jit"] = info
    suite.facts["jit_state"] = h.jit_snapshot()
    suite.write_sidecar()


if __name__ == "__main__":
    main()
