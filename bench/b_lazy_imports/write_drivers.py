from __future__ import annotations

import os

from bench.b_lazy_imports.constants import MARKER


def write_drivers(root: str, n: int) -> tuple[str, str]:
    """Two scripts in the module directory: imports alone, and imports plus facts."""
    imports = "".join(f"import genmod{i}\n" for i in range(n))
    only = os.path.join(root, "_import_only.py")
    with open(only, "w") as fh:
        fh.write(imports)
    facts = os.path.join(root, "_with_facts.py")
    with open(facts, "w") as fh:
        fh.write(
            imports
            + "import builtins, sys, time\n"
            + f"executed = getattr(builtins, '{MARKER}', 0)\n"
            + "t0 = time.perf_counter()\n"
            + "genmod0.value(7)\n"
            + "first_touch_ms = (time.perf_counter() - t0) * 1e3\n"
            + f"after = getattr(builtins, '{MARKER}', 0)\n"
            + "flag = bool(getattr(sys.flags, 'lazy_imports', False))\n"
            + "print('@@FACTS@@', flag, executed, after, first_touch_ms)\n"
        )
    return only, facts
