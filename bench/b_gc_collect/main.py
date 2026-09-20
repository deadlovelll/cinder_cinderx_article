import gc
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from bench.b_gc_collect.build import build
from bench.b_gc_collect.constants import N_GARBAGE, N_NODES
from bench.b_gc_collect.make_cycles import make_cycles
from bench.harness import cx_pyperf as h


h.boot(pin="threads")


def main() -> None:
    suite = h.Suite("b_gc_collect", forward=("visibility", "garbage"))
    suite.runner.argparser.add_argument(
        "--visibility", choices=("visible", "frozen", "immortal"), default="visible",
        help="per-process: immortalize_heap() cannot be undone")
    suite.runner.argparser.add_argument(
        "--garbage", type=int, default=N_GARBAGE,
        help="objects of cyclic garbage rebuilt before each collection; 0 for none")
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

    threads_list = [0] + ([h.usable_cpus()] if has_parallel else [])

    configured: int | None = None
    for garbage in ((0, args.garbage) if args.garbage else (0,)):
      for threads in threads_list:
        def timed(loops: int, threads: int = threads, garbage: int = garbage) -> float:
            nonlocal configured
            if configured == threads:
                pass
            elif has_parallel:
                cx.disable_parallel_gc()
            if threads and configured != threads:
                cx.enable_parallel_gc(min_generation=2, num_threads=threads)
                suite.facts.setdefault("parallel_settings_seen", {})[str(threads)] = (
                    cx.get_parallel_gc_settings())
            configured = threads
            total = 0.0
            for _ in range(loops):
                trash = make_cycles(garbage) if garbage else None
                del trash
                gc.disable()
                t0 = time.perf_counter()
                gc.collect()
                total += time.perf_counter() - t0
                gc.enable()
            return total

        work = "reclaim" if garbage else "traverse"
        impl = f"{visibility}/{work}/{'par' + str(threads) if threads else 'serial'}"
        suite.bench_time(case="gc_collect", impl=impl, time_fn=timed,
                         params={"nodes": N_NODES, "visibility": visibility,
                                 "threads": threads, "garbage": garbage},
                         note=("live graph only, so this is traversal cost" if not garbage
                               else f"{garbage} objects of cyclic garbage per collection"))

    suite.machine_probe()
    suite.facts["visibility"] = visibility
    suite.facts["live_nodes"] = len(nodes)
    suite.facts["gc_stats"] = gc.get_stats()
    suite.facts["parallel_available"] = has_parallel
    suite.facts["runtime_metrics"] = h.runtime_metrics()
    suite.write_sidecar()


if __name__ == "__main__":
    main()
