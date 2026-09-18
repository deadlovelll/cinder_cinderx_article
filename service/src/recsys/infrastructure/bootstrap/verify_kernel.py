from __future__ import annotations

from recsys.infrastructure.bootstrap.bootstrap_report import BootstrapReport


def verify_kernel(report: BootstrapReport) -> None:
    from recsys.domain.kernels.kernel_name import kernel_name
    from recsys.domain.kernels.load_kernel import load_kernel

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

    if report.embeddings_requested == "static":
        from recsys.domain.kernels import similar_static

        try:
            from _static import is_static_module

            report.embeddings_is_static = bool(is_static_module(similar_static))
        except ImportError:
            report.embeddings_is_static = False
        if not report.embeddings_is_static:
            report.problems.append(
                "embeddings=static but the module is not static: the loader was "
                "not installed before the import")
