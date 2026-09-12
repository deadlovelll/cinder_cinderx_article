"""What each half of the installation actually buys (plan 7.11)."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

COMBOS = ("both", "loader", "evaluator", "neither")
N = 200_000
REPS = 5


def run_combo(combo: str) -> dict:
    """Set up exactly one combination, then observe what the module became."""
    evaluator = combo in ("both", "evaluator")
    loader = combo in ("both", "loader")

    if evaluator or loader:
        import cinderx
        import cinderx.jit

        cinderx.jit.disable()
        if evaluator:
            cinderx.install_frame_evaluator()
        if loader:
            from cinderx.compiler.strict.loader import install

            install()

    import bench.kernels.prim_static as ps

    static_module = static_callable = None
    if evaluator or loader:
        from _static import is_static_callable, is_static_module

        static_module = bool(is_static_module(ps))
        static_callable = bool(is_static_callable(ps.sum_primitive))

    expected = (N - 1) * N // 2
    got = ps.sum_boxed(N)
    samples = []
    for _ in range(REPS):
        t0 = time.perf_counter()
        ps.sum_boxed(N)
        samples.append((time.perf_counter() - t0) * 1e3)
    samples.sort()

    return {
        "combo": combo, "frame_evaluator": evaluator, "loader": loader,
        "is_static_module": static_module, "is_static_callable": static_callable,
        "correct": got == expected,
        "median_ms": samples[len(samples) // 2], "min_ms": samples[0],
        "note": "timing is indicative only: this is an observation bench, "
                "the durations are not pyperf measurements",
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--combo", choices=COMBOS)
    ap.add_argument("--emit-json", action="store_true")
    args = ap.parse_args()

    if args.combo:
        res = run_combo(args.combo)
        if args.emit_json:
            print("@@RESULT@@" + json.dumps(res), flush=True)
        return

    # aggregation run: import the harness only here, so the per-combo children
    from bench.harness import cx_pyperf as h

    h.boot("stock")
    from bench.harness.facts import FactsRun

    run = FactsRun("b_install_order")
    results = []
    for combo in COMBOS:
        proc = subprocess.run(
            [sys.executable, os.path.abspath(__file__), "--combo", combo,
             "--emit-json"],
            capture_output=True, text=True, timeout=600, env={**os.environ},
        )
        line = next((l for l in proc.stdout.splitlines()
                     if l.startswith("@@RESULT@@")), None)
        if line is None:
            run.unavailable(case=f"install_order/{combo}", note=proc.stderr[-300:])
            continue
        res = json.loads(line[len("@@RESULT@@"):])
        results.append(res)
        run.log(f"  {combo:<10} evaluator={str(res['frame_evaluator']):<5} "
                f"loader={str(res['loader']):<5} "
                f"is_static_module={str(res['is_static_module']):<5} "
                f"{res['median_ms']:8.1f} ms")
    run.record("combos", results)
    run.write()


if __name__ == "__main__":
    main()
