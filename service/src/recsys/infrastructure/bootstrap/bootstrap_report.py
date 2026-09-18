
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Any

from recsys.settings import Settings


@dataclass(slots=True)
class BootstrapReport:

    mode: str
    cpython_jit: bool = False
    frame_evaluator: bool = False
    static_loader: bool = False
    kernel_requested: str = "plain"
    kernel_actual: str = "plain"
    kernel_is_static: bool | None = None
    embeddings_requested: str = "numpy"
    embeddings_is_static: bool | None = None
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
