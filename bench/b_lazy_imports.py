"""Lazy imports: what is not executed (plan 7.12)."""

from __future__ import annotations

import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bench.harness import cx_pyperf as h

h.boot()

MARKER = "_cx_bodies_executed"


def generate(root: str, n: int) -> None:
    """N modules with a body heavy enough to be worth deferring."""
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


def import_script(n: int) -> str:
    """Run in a child: import everything, then report what actually executed."""
    return (
        "import builtins, sys, time\n"
        f"mods = [__import__('genmod%d' % i) for i in range({n})]\n"
        f"executed = getattr(builtins, '{MARKER}', 0)\n"
        "t0 = time.perf_counter()\n"
        "mods[0].value(7)\n"
        "first_touch_ms = (time.perf_counter() - t0) * 1e3\n"
        f"after = getattr(builtins, '{MARKER}', 0)\n"
        "print('@@FACTS@@', executed, after, first_touch_ms)\n"
    )


def main() -> None:
    suite = h.Suite("b_lazy_imports", forward=("modules",))
    suite.runner.argparser.add_argument("--modules", type=int, default=200)
    args = suite.parse()
    n = args.modules

    if not hasattr(sys.flags, "lazy_imports"):
        suite.unavailable(case="lazy_imports", impl=h.config(),
                          note="sys.flags.lazy_imports absent: needs the meta fork")
        suite.facts["modules"] = n
        suite.write_sidecar()
        return

    root = os.path.join(h.RESULTS, f"_genmods_{suite.label}")
    generate(root, n)
    env_path = os.pathsep.join([root, os.environ.get("PYTHONPATH", "")]).rstrip(os.pathsep)

    try:
        # whole-process timing: this is start-up, not steady state
        suite.bench_command(
            case="lazy_imports", impl=f"{h.config()}/import_{n}",
            command=[sys.executable, "-c", f"[__import__('genmod%d' % i) for i in range({n})]"],
            params={"modules": n},
            note=f"PYTHONPATH={root}; whole process, import latency")

        # the observation: how many bodies ran, and what the first touch costs
        import subprocess

        proc = subprocess.run([sys.executable, "-c", import_script(n)],
                              capture_output=True, text=True, timeout=600,
                              env={**os.environ, "PYTHONPATH": env_path})
        line = next((l for l in proc.stdout.splitlines()
                     if l.startswith("@@FACTS@@")), None)
        if line:
            _, executed, after, first_touch = line.split()
            suite.facts["bodies_executed_after_import"] = int(executed)
            suite.facts["bodies_executed_after_first_touch"] = int(after)
            suite.facts["deferred"] = n - int(executed)
            suite.facts["first_touch_ms"] = float(first_touch)
            suite.log(f"  bodies executed: {executed}/{n}, "
                      f"first touch {float(first_touch):.3f} ms")
        else:
            suite.unavailable(case="lazy_imports", impl="bodies_executed",
                              note=proc.stderr[-300:])

        suite.facts["modules"] = n
        suite.facts["lazy_imports_flag"] = bool(sys.flags.lazy_imports)
        suite.write_sidecar()
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    main()
