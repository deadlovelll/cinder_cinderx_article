import gc
import json
import os
import statistics
import sys
import time

import cinderx


OUT = os.path.join(os.path.dirname(__file__), "par_gc_shape.json")
TOTAL_REFS = 2_000_000
WIDTHS = (3, 10, 30, 100)
THREADS = (0, 1, 2, 4, 8)
REPS = 7
LAUNCHES = 5


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
    raw = {w: {t: [] for t in THREADS} for w in WIDTHS}
    for _ in range(LAUNCHES):
        for width in WIDTHS:
            n = TOTAL_REFS // width
            for t in THREADS:
                raw[width][t].append(collect_ms(n, width, t))
        print(".", end="", flush=True)
    print()

    rows = []
    for width in WIDTHS:
        row = {"refs_per_object": width, "objects": TOTAL_REFS // width}
        for t in THREADS:
            vals = raw[width][t]
            row[f"t{t}"] = statistics.median(vals)
            row[f"t{t}_lo"], row[f"t{t}_hi"] = min(vals), max(vals)
        for t in THREADS[1:]:
            row[f"ratio{t}"] = row[f"t{t}"] / row["t0"]
        rows.append(row)
        print(f"  ссылок/объект {width:>4}  объектов {row['objects']:>8}"
              f"  посл. {row['t0']:6.1f}  "
              + "  ".join(f"п{t}={row[f't{t}']:6.1f} {row[f'ratio{t}']:5.2f}x"
                          for t in THREADS[1:]))
        sys.stdout.flush()

    json.dump({"total_refs": TOTAL_REFS, "reps": REPS, "launches": LAUNCHES,
               "cpus": sorted(os.sched_getaffinity(0)), "rows": rows},
              open(OUT, "w"), indent=1, ensure_ascii=False)
    print("->", OUT)


if __name__ == "__main__":
    main()
