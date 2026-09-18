from __future__ import annotations

from recsys.domain.kernels.kernel_mode import KERNEL_MODE


def load_kernel():
    if KERNEL_MODE == "static":
        from recsys.domain.kernels import walk_static

        return walk_static
    from recsys.domain.kernels import walk_plain

    return walk_plain
