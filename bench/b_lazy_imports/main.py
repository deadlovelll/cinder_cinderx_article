"""Lazy imports: what is not executed (plan 7.12)."""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from bench.b_lazy_imports.bodies_loaded import bodies_loaded
from bench.b_lazy_imports.constants import LAZY_ENV
from bench.b_lazy_imports.gen_package import gen_package
from bench.b_lazy_imports.generate import generate
from bench.b_lazy_imports.write_drivers import write_drivers
from bench.harness import cx_pyperf as h


h.boot()


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

    root = os.path.join(h.RESULTS, f"_genmods_{suite.label}_{os.getpid()}")
    generate(root, n)
    import_only, with_facts = write_drivers(root, n)
    env_path = os.pathsep.join([root, os.environ.get("PYTHONPATH", "")]).rstrip(os.pathsep)
    os.environ["PYTHONPATH"] = env_path

    import subprocess

    try:
        for leg, lazy in (("eager", False), ("lazy", True)):
            os.environ.pop(LAZY_ENV, None)
            if lazy:
                os.environ[LAZY_ENV] = "1"

            suite.bench_command(
                case="lazy_imports", impl=f"{h.config()}/{leg}_{n}",
                command=[sys.executable, import_only],
                params={"modules": n, "lazy": lazy},
                note=f"PYTHONPATH={root}; {LAZY_ENV}={'1' if lazy else 'unset'}; "
                     f"whole process, import latency")

            proc = subprocess.run([sys.executable, with_facts],
                                  capture_output=True, text=True, timeout=600,
                                  env={**os.environ, "PYTHONPATH": env_path})
            line = next((l for l in proc.stdout.splitlines()
                         if l.startswith("@@FACTS@@")), None)
            if line:
                _, flag, executed, after, first_touch = line.split()
                suite.facts[leg] = {
                    "lazy_imports_flag": flag == "True",
                    "bodies_executed_after_import": int(executed),
                    "bodies_executed_after_first_touch": int(after),
                    "deferred": n - int(executed),
                    "first_touch_ms": float(first_touch),
                }
                suite.log(f"  {leg:<5} flag={flag:<5} bodies executed: {executed}/{n}, "
                          f"first touch {float(first_touch):.3f} ms")
            else:
                suite.unavailable(case="lazy_imports", impl=f"bodies_executed/{leg}",
                                  note=proc.stderr[-300:])

        os.environ.pop(LAZY_ENV, None)

        import importlib
        import time as _time

        names, stmt = gen_package(root, n)
        sys.path.insert(0, root)

        def purge() -> None:
            for name in names:
                sys.modules.pop(name, None)

        def timed(loops: int, lazy: bool) -> float:
            if lazy:
                importlib.set_lazy_imports()
            total = 0.0
            for _ in range(loops):
                purge()
                ns: dict = {}
                t0 = _time.perf_counter()
                exec(stmt, ns)
                total += _time.perf_counter() - t0
            return total

        suite.bench_time(case="import_in_process", impl=f"{h.config()}/eager",
                         time_fn=lambda loops: timed(loops, False),
                         params={"modules": n},
                         note="one import statement over a package of n modules; "
                              "every body runs")
        purge()
        suite.facts["in_process_eager_bodies"] = bodies_loaded(n)

        if hasattr(importlib, "set_lazy_imports"):
            suite.bench_time(case="import_in_process", impl=f"{h.config()}/lazy",
                             time_fn=lambda loops: timed(loops, True),
                             params={"modules": n},
                             note="the same statement with importlib.set_lazy_imports(); "
                                  "no body runs until something is touched")
            importlib.set_lazy_imports()
            purge()
            ns: dict = {}
            exec(stmt, ns)
            deferred = n - bodies_loaded(n)
            t0 = _time.perf_counter()
            ns["m"].touch_one()
            suite.facts["in_process_first_touch_ms"] = (_time.perf_counter() - t0) * 1e3
            suite.facts["in_process_lazy_deferred"] = deferred
            suite.log(f"  in-process: deferred {deferred}/{n}, first touch "
                      f"{suite.facts['in_process_first_touch_ms']:.3f} ms")
        else:
            suite.unavailable(case="import_in_process", impl=f"{h.config()}/lazy",
                              note="importlib.set_lazy_imports() absent: needs the fork")

        suite.facts["modules"] = n
        suite.facts["lazy_imports_flag"] = bool(sys.flags.lazy_imports)
        suite.write_sidecar()
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    main()
