"""Inline cache inheritance: how much prior execution the JIT needs (plan 7.4)."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bench.harness import cx_pyperf as h

h.boot()

N_ITEMS = 2_000
ROUNDS = 40


class Cell:
    __slots__ = ("v",)

    def __init__(self, v: int) -> None:
        self.v = v

    def bump(self, d: int) -> int:
        self.v = self.v + d
        return self.v


def hot_attr(cells: list, rounds: int) -> int:
    # the reset makes the function idempotent, which it has to be: pyperf calls
    for c in cells:
        c.v = 0
    total = 0
    for _ in range(rounds):
        for c in cells:
            total += c.bump(1)
    return total


def hot_index(buf: list, rounds: int) -> int:
    total = 0
    n = len(buf)
    for r in range(rounds):
        i = 0
        while i < n:
            total += buf[i] * buf[n - 1 - i] + r
            i += 1
    return total


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

    # The reference is computed in closed form, never by calling the target:
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

    # the caches fill here, or do not.
    for _ in range(warmup):
        work()
    before = h.jit().count_interpreted_calls(hot)
    info = h.compile_now(hot, warmup=0)

    # verification comes after compilation on purpose: the invariant this bench
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
