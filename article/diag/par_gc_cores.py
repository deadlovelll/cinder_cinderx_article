import gc
import json
import os
import statistics
import sys
import time

import cinderx


OUT = os.path.join(os.path.dirname(__file__), "par_gc_cores.json")
N = 1_000_000
WIDTH = 100
REPS = 7
LAUNCHES = 3
ARMS = (
    ("все 16 ядер", tuple(range(16)), 0),
    ("все 16 ядер", tuple(range(16)), 8),
    ("все 16 ядер", tuple(range(16)), 16),
    ("14 ядер без 0.7 ГГц", tuple(range(14)), 0),
    ("14 ядер без 0.7 ГГц", tuple(range(14)), 8),
    ("14 ядер без 0.7 ГГц", tuple(range(14)), 14),
)


def fat(n, width):
    groups = [[None] * width for _ in range(n)]
    for i, g in enumerate(groups):
        for j in range(width):
            g[j] = groups[(i + j) % n]
    return groups


def collect_ms(cpus, threads):
    os.sched_setaffinity(0, cpus)
    if cinderx.has_parallel_gc():
        cinderx.disable_parallel_gc()
    if threads:
        cinderx.enable_parallel_gc(min_generation=2, num_threads=threads)
    live = fat(N, WIDTH)
    gc.collect()
    best = float("inf")
    for _ in range(REPS):
        t0 = time.perf_counter()
        gc.collect()
        best = min(best, (time.perf_counter() - t0) * 1e3)
    del live
    gc.collect()
    if cinderx.has_parallel_gc():
        cinderx.disable_parallel_gc()
    return best


def main():
    acc = {i: [] for i in range(len(ARMS))}
    for _ in range(LAUNCHES):
        for i, (_label, cpus, threads) in enumerate(ARMS):
            acc[i].append(collect_ms(cpus, threads))
        print(".", end="", flush=True)
    print()

    rows = []
    base = {}
    for i, (label, cpus, threads) in enumerate(ARMS):
        ms = statistics.median(acc[i])
        if threads == 0:
            base[label] = ms
        rows.append({"cores": label, "ncpu": len(cpus), "threads": threads,
                     "ms": ms, "ratio": ms / base[label]})
        tag = "последовательно" if threads == 0 else f"потоков {threads}"
        print(f"  {label:22} {tag:>16}  {ms:7.1f} мс  {ms / base[label]:5.2f}x")
        sys.stdout.flush()

    json.dump({"objects": N, "width": WIDTH, "reps": REPS,
               "launches": LAUNCHES, "rows": rows},
              open(OUT, "w"), indent=1, ensure_ascii=False)
    print("->", OUT)


if __name__ == "__main__":
    main()
