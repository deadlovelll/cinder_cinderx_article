import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from bench.harness import cx_pyperf as h

h.boot("cinderx_jit")

from bench.b_jit_warmup.cell import Cell
from bench.b_jit_warmup.constants import N_ITEMS, ROUNDS
from bench.b_jit_warmup.hot_attr import hot_attr
from bench.b_jit_warmup.hot_index import hot_index

jit = h.jit()
REPS = 12
shape = sys.argv[1]
warm = int(sys.argv[2])

if shape == "attr":
    cells = [Cell(i) for i in range(N_ITEMS)]
    hot = hot_attr
    work = lambda: hot_attr(cells, ROUNDS)
else:
    buf = [i * 3 % 101 for i in range(N_ITEMS)]
    hot = hot_index
    work = lambda: hot_index(buf, ROUNDS)

for _ in range(warm):
    work()
jit.force_compile(hot)

before = jit.count_interpreted_calls(hot)
t = []
for _ in range(REPS):
    t0 = time.perf_counter()
    work()
    t.append((time.perf_counter() - t0) * 1e3)
after = jit.count_interpreted_calls(hot)
print("%-6s прогрев=%-3d  медиана %6.2f мс   интерпретировано %2d из %d   код %d Б"
      % (shape, warm, statistics.median(t), after - before, REPS,
         jit.get_compiled_size(hot)))
