from __future__ import annotations

import os
from pathlib import Path


ROOT = str(Path(__file__).resolve().parents[3])
RESULTS = os.environ.get("BENCH_RESULTS_DIR") or os.path.join(ROOT, "results", "pyperf")
CONFIGS = ("stock", "cinderx", "static", "cinderx_jit", "static_jit")
_CONFIG_ENV = "CX_BENCH_CONFIG"
