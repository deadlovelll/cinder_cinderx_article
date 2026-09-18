from __future__ import annotations

from recsys.infrastructure.bootstrap.bootstrap_report import BootstrapReport
from recsys.settings import Settings


def prepare_for_fork(settings: Settings, report: BootstrapReport,
                     hot_functions: list[Any]) -> None:
    if settings.cinderx_mode == "off":
        return
    try:
        import cinderx
        import cinderx.jit as jit
    except ImportError as exc:
        report.problems.append(f"cinderx unavailable: {exc}")
        return

    if settings.precompile and jit.is_enabled():
        compiled = 0
        for fn in hot_functions:
            try:
                if jit.force_compile(fn):
                    compiled += 1
            except Exception as exc:
                report.problems.append(f"force_compile failed for {fn!r}: {exc}")
        report.precompiled = compiled

    if settings.perf_trampoline:
        try:
            cinderx._compile_perf_trampoline_pre_fork()
            report.perf_trampoline = True
        except Exception as exc:
            report.problems.append(f"perf trampoline: {exc}")

    if settings.immortalize:
        cinderx.immortalize_heap()
        report.immortalized = True

    if settings.parallel_gc:
        if not cinderx.has_parallel_gc():
            report.problems.append("parallel GC requested but absent from this build")
        elif not settings.immortalize:
            report.problems.append(
                "parallel GC enabled without immortalisation: the collector "
                "parallelises traversal only, so with the heap still visible this "
                "is a measured loss, not a gain")
            cinderx.enable_parallel_gc(min_generation=2, num_threads=settings.parallel_gc_threads)
            report.parallel_gc = True
            report.parallel_gc_settings = cinderx.get_parallel_gc_settings()
        else:
            cinderx.enable_parallel_gc(min_generation=2, num_threads=settings.parallel_gc_threads)
            report.parallel_gc = True
            report.parallel_gc_settings = cinderx.get_parallel_gc_settings()
