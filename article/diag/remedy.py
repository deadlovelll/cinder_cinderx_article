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
REPS = 12
how = sys.argv[1]
WARM = 4


def work():
    return hot_index(buf, ROUNDS)


for _ in range(WARM):
    work()

if how == "force":
    jit.force_compile(hot_index)
elif how == "precompile":
    jit.precompile_all(workers=4)
elif how == "auto":
    jit.compile_after_n_calls(2)
    for _ in range(8):
        work()
elif how == "none":
    pass

before = jit.count_interpreted_calls(hot_index)
t = []
for _ in range(REPS):
    t0 = time.perf_counter()
    work()
    t.append((time.perf_counter() - t0) * 1e3)
after = jit.count_interpreted_calls(hot_index)
print("%-11s is_jit=%-6s код=%-5s  медиана %5.2f мс   интерпретировано %2d из %d"
      % (how, jit.is_jit_compiled(hot_index), jit.get_compiled_size(hot_index),
         statistics.median(t), after - before, REPS))
