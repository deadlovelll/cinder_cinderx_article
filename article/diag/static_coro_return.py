import asyncio
import os
import subprocess
import sys
import tempfile


SOURCE = """
import __static__
from __static__ import box, int64


async def primitive(x: int64, n: int64) -> int64:
    t: int64 = 0
    i: int64 = 0
    while i < n:
        t = t + x * i
        i = i + 1
    return t


async def boxed(x: int64, n: int64) -> int:
    t: int64 = 0
    i: int64 = 0
    while i < n:
        t = t + x * i
        i = i + 1
    return box(t)
"""

CHILD = """
import asyncio, sys
import cinderx, cinderx.jit as jit
cinderx.install_frame_evaluator()
from cinderx.compiler.strict.loader import install
install()
if sys.argv[2] == "jit":
    jit.enable()
else:
    jit.disable()
sys.path.insert(0, sys.argv[1])
import k_coro as k
fn = getattr(k, sys.argv[3])
if sys.argv[2] == "jit":
    jit.force_compile(fn)
print("returns", type(fn(3, 8)).__name__)
async def drive():
    return await fn(3, 8)
try:
    print("await", asyncio.run(drive()))
except Exception as exc:
    print("await", type(exc).__name__, exc)
"""


def main() -> None:
    root = tempfile.mkdtemp(prefix="cx_coro_")
    with open(os.path.join(root, "k_coro.py"), "w") as fh:
        fh.write(SOURCE)
    child = os.path.join(root, "_child.py")
    with open(child, "w") as fh:
        fh.write(CHILD)

    print(f"{'return type':<14}{'jit':<6}{'call returns':<16}await")
    for name, shown in (("primitive", "int64"), ("boxed", "int")):
        for mode in ("nojit", "jit"):
            out = subprocess.run([sys.executable, child, root, mode, name],
                                 capture_output=True, text=True)
            lines = dict(l.split(" ", 1) for l in out.stdout.splitlines() if " " in l)
            print(f"{shown:<14}{mode:<6}{lines.get('returns', '-'):<16}"
                  f"{lines.get('await', out.stderr.strip()[:60] or '-')}")


if __name__ == "__main__":
    main()
