import gc
import json
import os
import statistics
import sys
import time

import cinderx


OUT = os.path.join(os.path.dirname(__file__), "par_gc_small_host.json")
WIDTH = 100
SIZES = (100_000, 400_000)
REPS = 7
LAUNCHES = 3

HOSTS = (
    ("4 ядра", (2, 3, 4, 5), (0, 2)),
    ("2 ядра", (2, 3), (0, 1)),
)


def fat(n, width):
    groups = [[None] * width for _ in range(n)]
    for i, g in enumerate(groups):
        for j in range(width):
            g[j] = groups[(i + j) % n]
    return groups


def collect_ms(n, width, cpus, threads):
    os.sched_setaffinity(0, cpus)
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
    print("дефолт num_threads = половина ядер машины, не меньше одного")
    print(f"объектов {SIZES}, ссылок на объект {WIDTH}, "
          f"повторов {REPS}, запусков {LAUNCHES}\n")

    acc = {}
    for _ in range(LAUNCHES):
        for host, cpus, thread_set in HOSTS:
            for n in SIZES:
                for t in thread_set:
                    acc.setdefault((host, n, t), []).append(
                        collect_ms(n, WIDTH, cpus, t))
        print(".", end="", flush=True)
    print("\n")

    rows = []
    for host, cpus, thread_set in HOSTS:
        seq_threads, par_threads = thread_set
        default = par_threads
        for n in SIZES:
            seq = statistics.median(acc[(host, n, seq_threads)])
            par = statistics.median(acc[(host, n, par_threads)])
            row = {"host": host, "ncpu": len(cpus), "cpus": list(cpus),
                   "objects": n, "refs": n * WIDTH,
                   "default_threads": default,
                   "sequential_ms": seq, "parallel_ms": par,
                   "parallel_lo": min(acc[(host, n, par_threads)]),
                   "parallel_hi": max(acc[(host, n, par_threads)]),
                   "slowdown": par / seq}
            rows.append(row)
            print(f"  {host}, объектов {n:>7}  дефолт {default} поток(а)  "
                  f"последовательно {seq:7.1f} мс   параллельно {par:7.1f} мс   "
                  f"хуже в {row['slowdown']:.2f} раза")
            sys.stdout.flush()

    os.sched_setaffinity(0, range(os.cpu_count()))
    json.dump({"what": "дефолтное число потоков на машине с 4 и 2 ядрами",
               "default_rule": "Ci_get_num_processors() / 2, минимум 1",
               "note": "дефолт воспроизведён явным num_threads: считает он "
                       "ядра машины, а не маску аффинити",
               "width": WIDTH, "reps": REPS, "launches": LAUNCHES,
               "rows": rows},
              open(OUT, "w"), indent=1, ensure_ascii=False)
    print("->", OUT)


if __name__ == "__main__":
    main()
