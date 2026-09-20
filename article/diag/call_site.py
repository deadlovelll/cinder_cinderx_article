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
n = N_ITEMS
buf = [i * 3 % 101 for i in range(n)]
REPS = 15


def bench(fn, label):
    before = jit.count_interpreted_calls(hot_index)
    times = []
    for _ in range(REPS):
        t0 = time.perf_counter()
        fn()
        times.append((time.perf_counter() - t0) * 1e3)
    after = jit.count_interpreted_calls(hot_index)
    print("  %-34s медиана %5.2f мс   интерпретировано %2d из %d"
          % (label, statistics.median(times), after - before, REPS))


def fresh_call_site():
    ns = {"hot_index": hot_index, "buf": buf, "ROUNDS": ROUNDS}
    exec("def caller():\n    return hot_index(buf, ROUNDS)\n", ns)
    return ns["caller"]


site_a = fresh_call_site()

for _ in range(2):
    site_a()

print("после двух прогревов через точку вызова A, force_compile:")
jit.force_compile(hot_index)
print("  is_jit_compiled =", jit.is_jit_compiled(hot_index),
      " code_bytes =", jit.get_compiled_size(hot_index))

bench(site_a, "прогретая точка вызова A")
bench(fresh_call_site(), "свежая точка вызова B")
bench(fresh_call_site(), "свежая точка вызова C")
bench(site_a, "снова прогретая A")
