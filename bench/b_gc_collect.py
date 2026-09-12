"""Collection cost against heap visibility and thread count (plan 7.14)."""

from __future__ import annotations

import gc
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bench.harness import cx_pyperf as h

h.boot()

N_NODES = 300_000


class Node:
    __slots__ = ("nxt", "prev", "payload")

    def __init__(self, payload) -> None:
        self.nxt = None
        self.prev = None
        self.payload = payload


def build(n: int) -> list:
    """A tracked cyclic graph the collector cannot untrack away, and no garbage."""
    nodes = [Node((i, [i, i + 1])) for i in range(n)]
    for i, node in enumerate(nodes):
        node.nxt = nodes[(i + 1) % n]
        node.prev = nodes[(i - 1) % n]
    return nodes


def main() -> None:
    suite = h.Suite("b_gc_collect", forward=("visibility",))
    suite.runner.argparser.add_argument(
        "--visibility", choices=("visible", "frozen", "immortal"), default="visible",
        help="per-process: immortalize_heap() cannot be undone")
    args = suite.parse()
    visibility = args.visibility

    cx = h.cinderx()
    if cx is None:
        suite.unavailable(case="gc_collect", impl=visibility,
                          note="needs a cinderx config")
        suite.write_sidecar()
        return

    nodes = build(N_NODES)
    gc.collect()

    if visibility == "frozen":
        gc.freeze()
    elif visibility == "immortal":
        cx.immortalize_heap()

    has_parallel = cx.has_parallel_gc()
    if not has_parallel:
        suite.unavailable(case="gc_collect", impl=f"{visibility}/parallel",
                          note="ENABLE_PARALLEL_GC is not set in this build")

    threads_list = [0] + ([os.cpu_count() or 4] if has_parallel else [])

    for threads in threads_list:
        def timed(loops: int, threads: int = threads) -> float:
            # the collector is configured outside the clock
            if threads:
                cx.enable_parallel_gc(min_generation=0, num_threads=threads)
            elif has_parallel:
                cx.disable_parallel_gc()
            total = 0.0
            for _ in range(loops):
                t0 = time.perf_counter()
                gc.collect()
                total += time.perf_counter() - t0
            return total

        impl = f"{visibility}/{'par' + str(threads) if threads else 'serial'}"
        suite.bench_time(case="gc_collect", impl=impl, time_fn=timed,
                         params={"nodes": N_NODES, "visibility": visibility,
                                 "threads": threads},
                         note="no garbage in the graph, so this is traversal cost")

    suite.machine_probe()
    suite.facts["visibility"] = visibility
    suite.facts["live_nodes"] = len(nodes)
    suite.facts["gc_stats"] = gc.get_stats()
    suite.facts["parallel_settings"] = (cx.get_parallel_gc_settings()
                                       if has_parallel else None)
    suite.facts["runtime_metrics"] = h.runtime_metrics()
    suite.write_sidecar()


if __name__ == "__main__":
    main()
