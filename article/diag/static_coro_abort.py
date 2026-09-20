import json
import os
import subprocess
import sys
import tempfile


OUT = os.path.join(os.path.dirname(__file__), "static_coro_abort.json")

SOURCE_PRIMITIVE = """
import __static__
from __static__ import box, int64


async def leaf(x: int64, n: int64) -> int64:
    t: int64 = 0
    i: int64 = 0
    while i < n:
        t = t + x * i
        i = i + 1
    return t


async def driver(x: int64, n: int64) -> int:
    v: int64 = await leaf(x, n)
    return box(v)
"""

SOURCE_BOXED = """
import __static__
from __static__ import box, int64


async def leaf(x: int64, n: int64) -> int:
    t: int64 = 0
    i: int64 = 0
    while i < n:
        t = t + x * i
        i = i + 1
    return box(t)


async def driver(x: int64, n: int64) -> int:
    v = await leaf(x, n)
    return v
"""

CHILD = """
import asyncio, sys
import cinderx, cinderx.jit as jit
cinderx.install_frame_evaluator()
from cinderx.compiler.strict.loader import install
install()
jit.enable()
sys.path.insert(0, sys.argv[1])
import k_abort as k
print("imported", flush=True)
jit.force_compile(k.driver)
print("compiled", flush=True)
print("result", asyncio.run(k.driver(3, 8)), flush=True)
"""

ASSERT_TEXT = "Only primitive numeric types should be boxed"


def run(source: str) -> dict:
    root = tempfile.mkdtemp(prefix="cx_abort_")
    with open(os.path.join(root, "k_abort.py"), "w") as fh:
        fh.write(source)
    child = os.path.join(root, "_child.py")
    with open(child, "w") as fh:
        fh.write(CHILD)
    out = subprocess.run([sys.executable, child, root],
                         capture_output=True, text=True, timeout=300)
    stages = [l for l in out.stdout.splitlines() if l]
    err = out.stderr.strip().splitlines()
    return {
        "returncode": out.returncode,
        "signal": -out.returncode if out.returncode < 0 else None,
        "reached": stages,
        "assert_text_seen": ASSERT_TEXT in out.stderr,
        "stderr_tail": err[-6:],
    }


def main() -> None:
    rows = []
    for label, source in (("примитивный возврат, int64", SOURCE_PRIMITIVE),
                          ("боксированный возврат, int", SOURCE_BOXED)):
        r = run(source)
        r["arm"] = label
        rows.append(r)
        state = ("упал: " + ("SIGABRT" if r["signal"] == 6 else str(r["returncode"]))
                 if r["returncode"] != 0 else "отработал")
        print(f"  {label:<28} {state:<16} ассерт в stderr: {r['assert_text_seen']}")
        for line in r["stderr_tail"]:
            print(f"      {line}")

    json.dump({"what": "await примитивной корутины внутри типизированного модуля",
               "assert_text": ASSERT_TEXT,
               "python": sys.executable,
               "rows": rows},
              open(OUT, "w"), indent=1, ensure_ascii=False)
    print("->", OUT)


if __name__ == "__main__":
    main()
