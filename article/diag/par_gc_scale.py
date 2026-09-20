import gc
import json
import os
import sys
import time

import cinderx


OUT = os.path.join(os.path.dirname(__file__), "par_gc_scale.json")
WIDTH = 100
SIZES = (20_000, 100_000, 400_000, 1_000_000)
SCALE_THREADS = (0, 1, 2, 4, 8, 16)
REPS = 7


def fat(n, width):
    groups = [[None] * width for _ in range(n)]
    for i, g in enumerate(groups):
        for j in range(width):
            g[j] = groups[(i + j) % n]
    return groups


def collect_ms(n, width, threads):
    if cinderx.has_parallel_gc():
        cinderx.disable_parallel_gc()
    if threads:
        cinderx.enable_parallel_gc(min_generation=2, num_threads=threads)
    live = fat(n, width)
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
    scale = []
    for n in SIZES:
        row = {"objects": n, "refs": n * WIDTH}
        for t in SCALE_THREADS:
            row[f"t{t}"] = collect_ms(n, WIDTH, t)
        for t in SCALE_THREADS[1:]:
            row[f"ratio{t}"] = row[f"t{t}"] / row["t0"]
        scale.append(row)
        print(f"  объектов {n:>8}  посл. {row['t0']:7.1f}"
              f"  " + "  ".join(f"п{t}={row[f't{t}']:7.1f} {row[f'ratio{t}']:4.2f}x" for t in SCALE_THREADS[1:]))
        sys.stdout.flush()

    json.dump({"width": WIDTH, "reps": REPS,
               "cpus": sorted(os.sched_getaffinity(0)),
               "scale": scale},
              open(OUT, "w"), indent=1, ensure_ascii=False)
    print("->", OUT)


if __name__ == "__main__":
    main()
