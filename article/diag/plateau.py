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
buf = [i * 3 % 101 for i in range(N_ITEMS)]
REPS = 15


def timed(label):
    t = []
    for _ in range(REPS):
        t0 = time.perf_counter()
        hot_index(buf, ROUNDS)
        t.append((time.perf_counter() - t0) * 1e3)
    print("  %-46s %5.2f мс" % (label, statistics.median(t)))


timed("до компиляции - чистый интерпретатор")
for _ in range(2):
    hot_index(buf, ROUNDS)
jit.force_compile(hot_index)
timed("после force_compile, та же точка вызова")
