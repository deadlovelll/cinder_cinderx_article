"""The configuration ladder (plan 7.3). One workload, every configuration."""

from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bench.harness import cx_pyperf as h

h.boot()  # ASLR off + re-exec, CPU pinning, CinderX configuration

W, H, GENERATIONS = 160, 160, 8


def main() -> None:
    suite = h.Suite("b_ladder")
    suite.parse()

    from bench.kernels import data, life_plain

    grid = data.life_grid(W, H)
    expected = life_plain.checksum(life_plain.run(grid, W, H, GENERATIONS), W, H)
    params = {"w": W, "h": H, "generations": GENERATIONS, "cells": W * H}

    if h.is_static():
        import bench.kernels.life_static as life

        fresh = life.from_list(grid, W * H)
        cells = life.from_list(grid, W * H)
        scratch = life.from_list([0] * (W * H), W * H)

        def reset() -> None:
            i = 0
            while i < W * H:
                cells[i] = fresh[i]
                i += 1

        def once():
            return life.run(cells, scratch, W, H, GENERATIONS)

        verify = lambda: life.checksum(once(), W, H)
        target = life.step
    else:
        state = {}

        def reset() -> None:
            state["cur"] = list(grid)

        def once():
            return life_plain.run(state["cur"], W, H, GENERATIONS)

        verify = lambda: life_plain.checksum(once(), W, H)
        target = life_plain.step

    reset()
    if not suite.gate(case="life", impl=h.config(), got=verify(), expected=expected):
        suite.write_sidecar()
        return

    jit_info = {}
    if h.jit_on():
        reset()
        jit_info = h.compile_now(target, warmup=1, run=once)
        reset()
        if not suite.gate(case="life", impl=f"{h.config()}/compiled",
                          got=verify(), expected=expected):
            suite.write_sidecar()
            return

    def timed(loops: int) -> float:
        """The rebuild is outside the clock; only the generations are timed."""
        total = 0.0
        for _ in range(loops):
            reset()
            t0 = time.perf_counter()
            once()
            total += time.perf_counter() - t0
        return total

    # runs in every worker as well as the master: a process that would produce
    reset()
    suite.check_once(("life", h.config()), verify, expected)

    suite.bench_time(case="life", impl=h.config(), time_fn=timed, params=params,
                     note=f"jit={jit_info.get('functions', {})}")
    suite.machine_probe()

    suite.facts["jit"] = jit_info
    suite.facts["jit_state"] = h.jit_snapshot()
    suite.facts["runtime_metrics"] = h.runtime_metrics()
    suite.facts["checksum"] = expected
    suite.write_sidecar()


if __name__ == "__main__":
    main()
