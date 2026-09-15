
from __future__ import annotations

import os

_MODE = os.environ.get("RECSYS_KERNEL", "plain").lower()


def kernel_name() -> str:
    return _MODE


def load_kernel():
    if _MODE == "static":
        from recsys.domain.kernels import walk_static

        return walk_static
    from recsys.domain.kernels import walk_plain

    return walk_plain
