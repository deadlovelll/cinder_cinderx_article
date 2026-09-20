import json
import os
import subprocess
import sys
import tempfile


OUT = os.path.join(os.path.dirname(__file__), "cached_property_cost.json")
N = 200_000
REPS = 7

PLAIN = """
import functools
from cinderx import cached_property as cx_cached_property


class Std:
    def __init__(self, n):
        self.n = n

    @functools.cached_property
    def x(self):
        return self.n * 2


class Cx:
    def __init__(self, n):
        self.n = n

    @cx_cached_property
    def x(self):
        return self.n * 2
"""

STATIC = """
import __static__
from cinderx import cached_property


class Slotted:
    n: int

    def __init__(self, n: int) -> None:
        self.n = n

    @cached_property
    def x(self) -> int:
        return self.n * 2
"""

LOOP = """
def read_prop(o, n: int) -> int:
    s = 0
    i = 0
    while i < n:
        s = s + o.x
        i = i + 1
    return s
"""

CHILD = """
import json, sys, time
import cinderx, cinderx.jit as jit

root, mode, leg, n, reps = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]), int(sys.argv[5])
cinderx.install_frame_evaluator()
from cinderx.compiler.strict.loader import install
install()
if mode == "jit":
    jit.enable()
    jit.compile_after_n_calls(0)
else:
    jit.disable()

sys.path.insert(0, root)
import k_loop
from k_loop import read_prop

if leg == "slot":
    import k_static
    obj = k_static.Slotted(3)
else:
    import k_plain
    obj = (k_plain.Std(3) if leg == "functools" else k_plain.Cx(3))

obj.x  # значение посчитано до замера: меряем только чтение готового

before = jit.count_interpreted_calls(read_prop)
best = float("inf")
for _ in range(reps):
    t0 = time.perf_counter()
    read_prop(obj, n)
    best = min(best, (time.perf_counter() - t0) * 1e9 / n)
after = jit.count_interpreted_calls(read_prop)

print(json.dumps({
    "ns_per_read": best,
    "interpreted_calls": after - before,
    "jit_compiled": jit.is_jit_compiled(read_prop),
    "storage": "slots" if not hasattr(obj, "__dict__") else "instance dict",
}))
"""


def run(root: str, child: str, mode: str, leg: str) -> dict:
    out = subprocess.run(
        [sys.executable, child, root, mode, leg, str(N), str(REPS)],
        capture_output=True, text=True, timeout=600)
    if out.returncode != 0:
        sys.exit(f"{leg}/{mode}: {out.stderr.strip()[-800:]}")
    return json.loads(out.stdout.strip().splitlines()[-1])


def main() -> None:
    root = tempfile.mkdtemp(prefix="cx_cprop_")
    for name, src in (("k_plain.py", PLAIN), ("k_static.py", STATIC),
                      ("k_loop.py", LOOP)):
        with open(os.path.join(root, name), "w") as fh:
            fh.write(src)
    child = os.path.join(root, "_child.py")
    with open(child, "w") as fh:
        fh.write(CHILD)

    legs = (("functools", "functools, словарь экземпляра"),
            ("cinderx", "cinderx, словарь экземпляра"),
            ("slot", "cinderx в типизированном модуле, слот"))
    rows = []
    print(f"{'нога':<44}{'без JIT':>12}{'под JIT':>12}   интерпр.")
    for leg, label in legs:
        row = {"leg": leg, "label": label}
        for mode in ("nojit", "jit"):
            r = run(root, child, mode, leg)
            row[f"ns_{mode}"] = r["ns_per_read"]
            row[f"interpreted_{mode}"] = r["interpreted_calls"]
            row[f"jit_compiled_{mode}"] = r["jit_compiled"]
            row["storage"] = r["storage"]
        rows.append(row)
        print(f"{label:<44}{row['ns_nojit']:>9.2f} нс{row['ns_jit']:>9.2f} нс"
              f"{row['interpreted_jit']:>10}")

    base = {r["leg"]: r for r in rows}
    ratios = {
        "functools/cinderx, под JIT":
            base["functools"]["ns_jit"] / base["cinderx"]["ns_jit"],
        "functools/слот, под JIT":
            base["functools"]["ns_jit"] / base["slot"]["ns_jit"],
        "functools/cinderx, без JIT":
            base["functools"]["ns_nojit"] / base["cinderx"]["ns_nojit"],
    }
    print()
    for k, v in ratios.items():
        print(f"  {k:<32} {v:.2f}x")

    json.dump({"what": "чтение уже посчитанного cached_property, нс на чтение",
               "reads_per_call": N, "reps": REPS,
               "note": "компиляция через compile_after_n_calls(0); "
                       "interpreted_calls под JIT должен быть 0",
               "rows": rows, "ratios": ratios},
              open(OUT, "w"), indent=1, ensure_ascii=False)
    print("->", OUT)


if __name__ == "__main__":
    main()
