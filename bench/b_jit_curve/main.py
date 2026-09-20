import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from bench.b_jit_curve.constants import GENERATIONS, H, W
from bench.harness import cx_pyperf as h, system
from bench.harness.facts import FactsRun


h.boot()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--iterations", type=int, default=400,
                    help="in-process iterations recorded in order")
    ap.add_argument("--jit-mode", choices=("auto", "forced", "off"), default="auto",
                    help="how compilation is triggered; 'auto' is what an "
                         "application gets, 'forced' is the compiler's ceiling")
    args = ap.parse_args()

    run = FactsRun("b_jit_curve", label=args.jit_mode)
    from bench.kernels import data, life_plain

    grid = data.life_grid(W, H)
    expected = life_plain.checksum(life_plain.run(grid, W, H, GENERATIONS), W, H)

    if h.is_static():
        import bench.kernels.life_static as life

        fresh = life.from_list(grid, W * H)
        cells = life.from_list(grid, W * H)
        scratch = life.from_list([0] * (W * H), W * H)

        def once():
            i = 0
            while i < W * H:
                cells[i] = fresh[i]
                i += 1
            return life.run(cells, scratch, W, H, GENERATIONS)

        digest = lambda out: life.checksum(out, W, H)
        target = life.step
    else:
        def once():
            return life_plain.run(list(grid), W, H, GENERATIONS)

        digest = lambda out: life_plain.checksum(out, W, H)
        target = life_plain.step

    jit_info: dict[str, object] = {"mode": args.jit_mode}
    cpython_jit = getattr(sys, "_jit", None)
    if cpython_jit is not None:
        jit_info["cpython_jit"] = {
            "available": cpython_jit.is_available(),
            "enabled": cpython_jit.is_enabled(),
            "note": "tier 2 has no per-function introspection: the curve is the "
                    "only witness that anything compiled",
        }
    if h.jit_on() and args.jit_mode == "auto":
        h.jit().auto()
    elif h.jit_on() and args.jit_mode == "forced":
        jit_info.update(h.compile_now(target, warmup=1, run=once))

    series = []
    for _ in range(args.iterations):
        t0 = time.perf_counter()
        out = once()
        series.append((time.perf_counter() - t0) * 1e3)

    if digest(out) != expected:
        run.unavailable(case="jit_curve", note="checksum mismatch; not classified")
        run.write()
        return

    verdict = system.classify_curve(series)
    trend = system.mann_kendall(series)

    if h.jit_on():
        jit_info.update({
            "is_jit_compiled": bool(h.jit().is_jit_compiled(target)),
            "interpreted_calls": h.jit().count_interpreted_calls(target),
            "compiled_total": len(h.jit().get_compiled_functions()),
        })

    run.record("params", {"w": W, "h": H, "generations": GENERATIONS,
                          "iterations": args.iterations})
    run.record("jit", jit_info)
    run.record("classification", verdict)
    run.record("whole_series_trend", trend)
    run.record("series_ms", series)
    run.record("runtime_metrics", h.runtime_metrics())

    segs = verdict.get("segments", [])
    run.log(f"  {h.config()}/{args.jit_mode}: {verdict['verdict']}  "
            f"segments={verdict.get('n_segments')}  "
            f"steady_from={verdict.get('steady_from')}  "
            f"final/best={verdict.get('final_over_best')}")
    for s in segs:
        run.log(f"      [{s['start']:4d}:{s['end']:4d}) mean={s['mean']:8.3f} ms "
                f"sd={s['sd']:.3f}")
    run.write()


if __name__ == "__main__":
    main()
