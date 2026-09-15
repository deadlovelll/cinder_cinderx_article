from __future__ import annotations

import os

from bench.b_lazy_imports.constants import MARKER


def generate(root: str, n: int) -> None:
    os.makedirs(root, exist_ok=True)
    for i in range(n):
        with open(os.path.join(root, f"genmod{i}.py"), "w") as fh:
            fh.write(
                "import builtins\n"
                f"builtins.{MARKER} = getattr(builtins, '{MARKER}', 0) + 1\n"
                f"TABLE = {{k: k * {i + 1} for k in range(256)}}\n"
                "def value(k):\n"
                "    return TABLE[k % 256]\n"
            )
