"""The CinderX pre-fork chain, and the proof that it did what was asked."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Any

from recsys.settings import Settings


@dataclass(slots=True)
class BootstrapReport:
    """What was asked for, and what the runtime actually did. Never inferred."""

    mode: str
    cpython_jit: bool = False
    frame_evaluator: bool = False
    static_loader: bool = False
    kernel_requested: str = "plain"
    kernel_actual: str = "plain"
    kernel_is_static: bool | None = None
    jit_enabled: bool = False
    compile_after_n_calls: int | None = None
    precompiled: int = 0
    immortalized: bool = False
    parallel_gc: bool = False
    parallel_gc_settings: dict[str, int] | None = None
    perf_trampoline: bool = False
    problems: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {k: getattr(self, k) for k in self.__slots__}


def install_runtime(settings: Settings) -> BootstrapReport:
    """Steps 1-2. Must run before the application package is imported."""
    report = BootstrapReport(mode=settings.cinderx_mode,
                             kernel_requested=settings.kernel)
    jit_module = getattr(sys, "_jit", None)
    report.cpython_jit = bool(jit_module and jit_module.is_enabled())
    if settings.cinderx_mode == "off":
        if settings.kernel == "static":
            report.problems.append(
                "kernel=static requested with cinderx_mode=off: the module would "
                "run as ordinary Python and the rung would duplicate `plain`")
        return report

    try:
        import cinderx
        import cinderx.jit
    except ImportError as exc:
        report.problems.append(f"cinderx unavailable: {exc}")
        return report

    cinderx.install_frame_evaluator()
    report.frame_evaluator = cinderx.is_frame_evaluator_installed()

    if settings.kernel == "static":
        from cinderx.compiler.strict.loader import install

        install()
        report.static_loader = True

    if settings.cinderx_mode in ("jit", "jit_static"):
        cinderx.jit.enable()
    else:
        cinderx.jit.disable()
    report.jit_enabled = cinderx.jit.is_enabled()
    report.compile_after_n_calls = cinderx.jit.get_compile_after_n_calls()
    return report


def verify_kernel(report: BootstrapReport) -> None:
    """Step 3's check: did the module that answered match what was asked for?"""
    from recsys.domain.kernels.registry import kernel_name, load_kernel

    module = load_kernel()
    report.kernel_actual = kernel_name()
    if report.kernel_requested == "static":
        try:
            from _static import is_static_module

            report.kernel_is_static = bool(is_static_module(module))
        except ImportError:
            report.kernel_is_static = False
        if not report.kernel_is_static:
            report.problems.append(
                "kernel=static but the module is not static: the loader was not "
                "installed before the import")


def prepare_for_fork(settings: Settings, report: BootstrapReport,
                     hot_functions: list[Any]) -> None:
    """Steps 5-9. Runs in the parent, after the application is fully imported."""
    if settings.cinderx_mode == "off":
        return
    try:
        import cinderx
        import cinderx.jit as jit
    except ImportError as exc:
        report.problems.append(f"cinderx unavailable: {exc}")
        return

    if settings.precompile and jit.is_enabled():
        # force_compile, not auto(): a handler under 1000 calls would never compile.
        compiled = 0
        for fn in hot_functions:
            try:
                if jit.force_compile(fn):
                    compiled += 1
            except Exception as exc:  # a single failure must not stop the boot
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
            cinderx.enable_parallel_gc(min_generation=2, num_threads=settings.workers)
            report.parallel_gc = True
            report.parallel_gc_settings = cinderx.get_parallel_gc_settings()
        else:
            cinderx.enable_parallel_gc(min_generation=2, num_threads=settings.workers)
            report.parallel_gc = True
            report.parallel_gc_settings = cinderx.get_parallel_gc_settings()


def after_fork_child() -> None:
    """Step 10. The JIT's own post-fork hook, before anything else runs."""
    try:
        import cinderjit

        cinderjit.after_fork_child()
    except Exception:
        pass
