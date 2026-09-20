import argparse
import gc
import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from bench.harness import cx_pyperf as h

h.boot("cinderx_jit")

from bench.b_jit_warmup.constants import N_ITEMS, ROUNDS
from bench.b_jit_warmup.hot_index import hot_index

jit = h.jit()


def decoy(buf: list, rounds: int) -> int:
    total = 0
    n = len(buf)
    for r in range(rounds):
        i = 0
        while i < n:
            total += buf[i] * buf[n - 1 - i] + r
            i += 1
    return total


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--warm-with", choices=("self", "decoy", "none"), default="self")
    ap.add_argument("--count", type=int, default=2)
    ap.add_argument("--reps", type=int, default=15)
    args = ap.parse_args()

    n = N_ITEMS
    buf = [i * 3 % 101 for i in range(n)]

    def work() -> int:
        return hot_index(buf, ROUNDS)

    if args.warm_with == "self":
        for _ in range(args.count):
            work()
    elif args.warm_with == "decoy":
        for _ in range(args.count):
            decoy(buf, ROUNDS)

    before_blocks = sys.getallocatedblocks()
    gc_count = gc.get_count()
    interp_calls = jit.count_interpreted_calls(hot_index)
    jit.force_compile(hot_index)

    times = []
    for _ in range(args.reps):
        t0 = time.perf_counter()
        work()
        times.append((time.perf_counter() - t0) * 1e3)

    after_calls = jit.count_interpreted_calls(hot_index)
    print(json.dumps({
        "warm_with": args.warm_with,
        "interpreted_calls_after_timing": after_calls,
        "interpreted_during_timing": after_calls - interp_calls,
        "still_jit_compiled": bool(jit.is_jit_compiled(hot_index)),
        "deopts": jit.get_and_clear_runtime_stats().get("deopt"),
        "count": args.count,
        "interpreted_calls_of_hot_index": interp_calls,
        "code_bytes": jit.get_compiled_size(hot_index),
        "allocated_blocks_at_compile": before_blocks,
        "gc_count_at_compile": list(gc_count),
        "ms_median": round(statistics.median(times), 3),
        "ms_min": round(min(times), 3),
    }))


if __name__ == "__main__":
    main()
