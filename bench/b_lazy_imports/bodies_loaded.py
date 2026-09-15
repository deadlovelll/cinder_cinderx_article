from __future__ import annotations

import sys

from bench.b_lazy_imports.constants import PKG


def bodies_loaded(n: int) -> int:
    return sum(1 for k in sys.modules
               if k.startswith(f"{PKG}.m") and k != f"{PKG}.main")
