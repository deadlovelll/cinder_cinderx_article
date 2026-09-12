"""Which candidate-generation kernel is in use, decided once at import."""

from __future__ import annotations

import os

_MODE = os.environ.get("RECSYS_KERNEL", "plain").lower()


def kernel_name() -> str:
    return _MODE


def load_kernel():
    """Return the kernel module. Falls back loudly, never silently."""
    if _MODE == "static":
        from recsys.domain.kernels import walk_static

        return walk_static
    from recsys.domain.kernels import walk_plain

    return walk_plain
