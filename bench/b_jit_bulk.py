"""Bulk compilation: blocking, parallel, background, AOT (plan 7.6)."""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bench.harness import cx_pyperf as h

h.boot()

from bench.harness.facts import FactsRun


def make_functions(n: int, salt: str) -> list:
    """N distinct functions of similar size; `salt` keeps batches from colliding."""
    ns: dict = {}
    for i in range(n):
        exec(
            f"def f_{salt}_{i}(a, b):\n"
            f"    t = {i}\n"
            f"    for k in range(4):\n"
            f"        t = t + a * {i + 1} - b // {i + 2} + k\n"
            f"        if t > {1000 + i}:\n"
            f"            t = t - {i + 3}\n"
            f"    return t\n",
            ns,
        )
    return [ns[f"f_{salt}_{i}"] for i in range(n)]


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

    # force_compile
    fns = make_functions(n, "force")
    for f in fns:
        f(3, 2)
    t0 = time.perf_counter()
    ok = sum(1 for f in fns if jit.force_compile(f))
    run.record("force", {"n": n, "compiled": ok,
                         "wall_ms": (time.perf_counter() - t0) * 1e3,
                         "after": snapshot()})

    # precompile_all
    fns = make_functions(n, "pre")
    for f in fns:
        f(3, 2)
    t0 = time.perf_counter()
    returned = jit.precompile_all(workers=os.cpu_count() or 4)
    run.record("precompile_all", {"n": n, "returned": bool(returned),
                                  "workers": os.cpu_count(),
                                  "wall_ms": (time.perf_counter() - t0) * 1e3,
                                  "after": snapshot()})

    # background
    if hasattr(jit, "background_compile"):
        fns = make_functions(n, "bg")
        jit.background_compile(True)
        t0 = time.perf_counter()
        for f in fns:
            f(3, 2)
            jit.force_compile(f)
        submit_ms = (time.perf_counter() - t0) * 1e3
        jit.wait_for_background_compiles()
        total_ms = (time.perf_counter() - t0) * 1e3
        jit.background_compile(False)
        run.record("background", {"n": n, "submit_ms": submit_ms,
                                  "wall_ms": total_ms, "after": snapshot()})
    else:
        run.unavailable(case="jit_bulk/background",
                        note="background_compile absent in this build")

    # AOT dump
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
