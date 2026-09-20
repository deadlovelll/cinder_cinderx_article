import gc
import json
import os
import statistics
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..",
                                "service", "src"))

import cinderx

from recsys.infrastructure.bundles.bundle_cache import BundleCache

OUT = os.path.join(os.path.dirname(__file__), "bundle_gc.json")
N_ITEMS = 100_000
DEGREE = 24
BUNDLES = 40_000
WIDTH = 128
THREADS = (0, 2, 4, 8)
REPS = 7
LAUNCHES = 3


class Csr:
    __slots__ = ("indptr", "indices", "weights", "n_items")


def fake_csr() -> Csr:
    indptr = [0] * (N_ITEMS + 1)
    indices, weights = [], []
    for i in range(N_ITEMS):
        for k in range(DEGREE):
            indices.append((i * 7 + k * 13) % N_ITEMS)
            weights.append(1 + (i + k) % 500)
        indptr[i + 1] = len(indices)
    csr = Csr()
    csr.indptr, csr.indices, csr.weights, csr.n_items = indptr, indices, weights, N_ITEMS
    return csr


def collect_ms(csr, threads: int) -> tuple[float, int, int]:
    if cinderx.has_parallel_gc():
        cinderx.disable_parallel_gc()
    gc.collect()
    cinderx.immortalize_heap()
    if threads:
        cinderx.enable_parallel_gc(min_generation=2, num_threads=threads)
    cache = BundleCache(items=BUNDLES, width=WIDTH)
    cache.warm(csr, N_ITEMS)
    gc.collect()
    best = float("inf")
    for _ in range(REPS):
        t0 = time.perf_counter()
        gc.collect()
        best = min(best, (time.perf_counter() - t0) * 1e3)
    tracked, refs = cache.tracked_objects(), cache.refs()
    del cache
    gc.collect()
    if cinderx.has_parallel_gc():
        cinderx.disable_parallel_gc()
    return best, tracked, refs


def main() -> None:
    csr = fake_csr()
    acc: dict[int, list[float]] = {t: [] for t in THREADS}
    shape = (0, 0)
    for _ in range(LAUNCHES):
        for t in THREADS:
            ms, tracked, refs = collect_ms(csr, t)
            acc[t].append(ms)
            shape = (tracked, refs)
        print(".", end="", flush=True)
    print()

    serial = statistics.median(acc[0])
    rows = []
    for t in THREADS:
        ms = statistics.median(acc[t])
        rows.append({"threads": t, "ms": ms, "speedup": serial / ms,
                     "lo": min(acc[t]), "hi": max(acc[t])})
        tag = "последовательно" if t == 0 else f"потоков {t}"
        print(f"  {tag:>16}  {ms:7.1f} мс   ускорение {serial / ms:4.2f}x")

    json.dump({"bundles": BUNDLES, "width": WIDTH,
               "tracked_objects": shape[0], "refs": shape[1],
               "reps": REPS, "launches": LAUNCHES,
               "cpus": sorted(os.sched_getaffinity(0)), "rows": rows},
              open(OUT, "w"), indent=1, ensure_ascii=False)
    print("->", OUT)


if __name__ == "__main__":
    main()
