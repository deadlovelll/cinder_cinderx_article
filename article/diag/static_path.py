import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from bench.harness import cx_pyperf as h

cfg = sys.argv[1]
warm = int(sys.argv[2])
h.boot(cfg)

jit = h.jit()
W = H = 64
GENS = 2
REPS = 10

if cfg.startswith("static"):
    from bench.kernels import life_static as life
else:
    from bench.kernels import life_plain as life

from bench.kernels.data import life_grid

src = life_grid(W, H)
if cfg.startswith("static"):
    grid = life.from_list(src, W * H)
    scratch = life.from_list([0] * (W * H), W * H)

    def work():
        return life.run(grid, scratch, W, H, GENS)
else:
    def work():
        return life.run(src, W, H, GENS)


for _ in range(warm):
    work()

before_compile = jit.count_interpreted_calls(life.step)
jit.force_compile(life.step)

before = jit.count_interpreted_calls(life.step)
t = []
for _ in range(REPS):
    t0 = time.perf_counter()
    work()
    t.append((time.perf_counter() - t0) * 1e3)
after = jit.count_interpreted_calls(life.step)

print("%-12s прогрев=%-3d вызовов до компиляции=%-4d  медиана %6.2f мс   "
      "интерпретировано %3d из %d   is_jit=%s"
      % (cfg, warm, before_compile, statistics.median(t),
         after - before, REPS * GENS, jit.is_jit_compiled(life.step)))
