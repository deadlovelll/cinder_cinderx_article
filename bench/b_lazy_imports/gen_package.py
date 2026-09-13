from __future__ import annotations

import os

from bench.b_lazy_imports.constants import PKG


def gen_package(root: str, n: int) -> tuple[list[str], object]:
    """A package whose main module imports n others, byte-compiled before timing."""
    import compileall

    pkg = os.path.join(root, PKG)
    os.makedirs(pkg, exist_ok=True)
    open(os.path.join(pkg, "__init__.py"), "w").close()
    for i in range(n):
        with open(os.path.join(pkg, f"m{i:03d}.py"), "w") as fh:
            fh.write(f"TABLE = {{k: k * {i + 1} for k in range(256)}}\n"
                     "def value():\n"
                     "    return sum(TABLE.values())\n"
                     "CONST = value()\n")
    with open(os.path.join(pkg, "main.py"), "w") as fh:
        for i in range(n):
            fh.write(f"from {PKG} import m{i:03d}\n")
        fh.write("\ndef touch_one():\n    return m000.CONST\n")
    compileall.compile_dir(pkg, quiet=2)
    names = [PKG, f"{PKG}.main"] + [f"{PKG}.m{i:03d}" for i in range(n)]
    return names, compile(f"import {PKG}.main as m", "<import_pkg>", "exec")
