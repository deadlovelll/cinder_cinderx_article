from __future__ import annotations

import subprocess
import sys
from typing import Any


def _aslr_empirical(trials: int = 3) -> dict[str, Any]:
    """The check that cannot be fooled: does a child map itself at the same place?"""
    probe = (
        "import sys;"
        "print([l.split('-')[0] for l in open('/proc/self/maps')"
        " if l.rstrip().endswith('[stack]') or ' r-xp ' in l][:1][0])"
    )
    seen = []
    for _ in range(trials):
        try:
            out = subprocess.run([sys.executable, "-c", probe],
                                 capture_output=True, text=True, timeout=30)
        except Exception:
            return {"layout_stable": None, "layout_samples": []}
        if out.returncode != 0:
            return {"layout_stable": None, "layout_samples": []}
        seen.append(out.stdout.strip())
    return {"layout_stable": len(set(seen)) == 1, "layout_samples": seen}
