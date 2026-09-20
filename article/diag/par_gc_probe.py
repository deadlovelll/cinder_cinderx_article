import gc
import json
import os
import statistics
import sys
import time

import cinderx


OUT = os.path.join(os.path.dirname(__file__), "par_gc_probe.json")
N_NODES = 300_000
N_GARBAGE = 300_000
REPS = 5
LAUNCHES = 5
CHURN_SECONDS = 1.0

ARMS = (
    ("выключен", False, None, None),
    ("min_gen=2, потоков 1", True, 2, 1),
    ("min_gen=2, потоков 2", True, 2, 2),
    ("min_gen=2, потоков 4", True, 2, 4),
    ("min_gen=0, потоков 1", True, 0, 1),
    ("min_gen=0, потоков 4", True, 0, 4),
)


class Node:
    __slots__ = ("left", "right", "payload")

    def __init__(self):
        self.left = None
        self.right = None
        self.payload = None


def build_live(n):
    nodes = [Node() for _ in range(n)]
    for i, node in enumerate(nodes):
        node.left = nodes[i - 1]
        node.right = nodes[(i + 1) % n]
    return nodes


def make_cycles(n):
    out = []
    for _ in range(n // 2):
        a, b = Node(), Node()
        a.left, b.left = b, a
        out.append(a)
    out.clear()


def time_full_collect(reps=REPS):
    samples = []
    for _ in range(reps):
        make_cycles(N_GARBAGE)
        t0 = time.perf_counter()
        gc.collect()
        samples.append((time.perf_counter() - t0) * 1e3)
    return min(samples)


def time_young_churn(seconds=CHURN_SECONDS):
    deadline = time.perf_counter() + seconds
    n = 0
    t0 = time.perf_counter()
    while time.perf_counter() < deadline:
        make_cycles(2000)
        n += 1
    return (time.perf_counter() - t0) / n * 1e3


def arm(enable, min_gen, threads):
    if cinderx.has_parallel_gc():
        cinderx.disable_parallel_gc()
    if enable:
        cinderx.enable_parallel_gc(min_generation=min_gen, num_threads=threads)
    live = build_live(N_NODES)
    gc.collect()
    full = time_full_collect()
    churn = time_young_churn()
    del live
    gc.collect()
    if cinderx.has_parallel_gc():
        cinderx.disable_parallel_gc()
    return full, churn


def main():
    print("параллельный сборщик доступен:", cinderx.has_parallel_gc())
    print(f"узлов {N_NODES}, мусора {N_GARBAGE}, порог gc {gc.get_threshold()}")
    print(f"запусков {LAUNCHES}, повторов сборки {REPS}\n")

    acc = {i: {"full": [], "churn": []} for i in range(len(ARMS))}
    for _ in range(LAUNCHES):
        for i, (_label, enable, min_gen, threads) in enumerate(ARMS):
            full, churn = arm(enable, min_gen, threads)
            acc[i]["full"].append(full)
            acc[i]["churn"].append(churn)
        print(".", end="", flush=True)
    print("\n")

    rows = []
    base_churn = None
    for i, (label, _enable, min_gen, threads) in enumerate(ARMS):
        full = statistics.median(acc[i]["full"])
        churn = statistics.median(acc[i]["churn"])
        if base_churn is None:
            base_churn = churn
        row = {"arm": label, "min_generation": min_gen, "threads": threads,
               "full_collect_ms": full,
               "churn_ms": churn,
               "churn_lo": min(acc[i]["churn"]), "churn_hi": max(acc[i]["churn"]),
               "churn_vs_off": churn / base_churn}
        rows.append(row)
        print(f"  {label:<24} полная сборка {full:8.2f} мс   "
              f"цикл аллокаций {churn:6.3f} мс "
              f"[{row['churn_lo']:.3f}..{row['churn_hi']:.3f}]  "
              f"{row['churn_vs_off']:5.2f}x")
        sys.stdout.flush()

    json.dump({"what": "аллокационный цикл и полная сборка по армам сборщика",
               "nodes": N_NODES, "garbage": N_GARBAGE,
               "reps": REPS, "launches": LAUNCHES,
               "churn_seconds": CHURN_SECONDS,
               "gc_threshold": list(gc.get_threshold()),
               "cpus": sorted(os.sched_getaffinity(0)),
               "rows": rows},
              open(OUT, "w"), indent=1, ensure_ascii=False)
    print("->", OUT)


if __name__ == "__main__":
    main()
