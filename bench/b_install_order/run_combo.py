from __future__ import annotations

import time

from bench.b_install_order.constants import N, REPS


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
