import argparse
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from bench.b_jit_bulk.constants import GEN_MODULE
from bench.b_jit_bulk.make_functions import make_functions
from bench.harness import cx_pyperf as h
from bench.harness.facts import FactsRun


h.boot(pin="threads")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--functions", type=int, default=200)
    args, _ = ap.parse_known_args()
    n = args.functions

    run = FactsRun("b_jit_bulk")
    if not h.jit_on():
        run.unavailable(case="jit_bulk", note="needs a JIT config")
        run.write()
        return

    jit = h.jit()

    def snapshot() -> dict:
        return {"compiled_total": len(jit.get_compiled_functions()),
                "compilation_time_us": jit.get_compilation_time(),
                "allocator": jit.get_allocator_stats()}

    fns = make_functions(n, "force")
    for f in fns:
        f(3, 2)
    t0 = time.perf_counter()
    ok = sum(1 for f in fns if jit.force_compile(f))
    run.record("force", {"n": n, "compiled": ok,
                         "wall_ms": (time.perf_counter() - t0) * 1e3,
                         "after": snapshot()})

    for i in range(n):
        jit.append_jit_list(f"{GEN_MODULE}:f_pre_{i}")
    fns = make_functions(n, "pre")
    before = snapshot()
    workers = h.usable_cpus()
    t0 = time.perf_counter()
    returned = jit.precompile_all(workers=workers)
    wall_ms = (time.perf_counter() - t0) * 1e3
    after = snapshot()
    compiled = after["compiled_total"] - before["compiled_total"]
    run.record("precompile_all", {"n": n, "returned": bool(returned),
                                  "workers": workers, "compiled": compiled,
                                  "wall_ms": wall_ms, "after": after})
    if compiled == 0:
        run.unavailable(case="jit_bulk/precompile_all",
                        note="compiled nothing: no unit was registered for it")

    import cinderjit

    out_dir = tempfile.mkdtemp(prefix="cx_aot_")
    path = os.path.join(out_dir, "bundle.elf")
    try:
        t0 = time.perf_counter()
        cinderjit.dump_elf(path)
        run.record("aot_dump", {"wall_ms": (time.perf_counter() - t0) * 1e3,
                                "bytes": os.path.getsize(path), "path": path,
                                "note": "load_aot_bundle runs in a fresh process; "
                                        "it is a start-up cost, measured elsewhere"})
    except Exception as exc:
        run.unavailable(case="jit_bulk/aot_dump", note=f"{type(exc).__name__}: {exc}")

    for name in ("force", "precompile_all", "background"):
        v = run.facts.get(name)
        if isinstance(v, dict):
            run.log(f"  {name:<16} {v.get('wall_ms', 0):9.1f} ms for {n} functions")
    run.write()


if __name__ == "__main__":
    main()
