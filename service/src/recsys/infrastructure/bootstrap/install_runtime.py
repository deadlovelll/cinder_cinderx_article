import sys

from recsys.infrastructure.bootstrap.bootstrap_report import BootstrapReport
from recsys.settings import Settings


def install_runtime(settings: Settings) -> BootstrapReport:
    report = BootstrapReport(mode=settings.cinderx_mode,
                             kernel_requested=settings.kernel,
                             embeddings_requested=settings.embeddings)
    jit_module = getattr(sys, "_jit", None)
    report.cpython_jit = bool(jit_module and jit_module.is_enabled())
    if settings.cinderx_mode == "off":
        if settings.kernel == "static":
            report.problems.append(
                "kernel=static requested with cinderx_mode=off: the module would "
                "run as ordinary Python and the rung would duplicate `plain`")
        if settings.embeddings == "static":
            report.problems.append(
                "embeddings=static requested with cinderx_mode=off: the module "
                "would run as ordinary Python and the rung would duplicate "
                "`python`")
        return report

    try:
        import cinderx
        import cinderx.jit
    except ImportError as exc:
        report.problems.append(f"cinderx unavailable: {exc}")
        return report

    cinderx.install_frame_evaluator()
    report.frame_evaluator = cinderx.is_frame_evaluator_installed()

    if settings.kernel == "static" or settings.embeddings == "static":
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
