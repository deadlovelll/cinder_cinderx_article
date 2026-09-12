"""The cost of porting, measured as what the compiler refuses (plan 7.8)."""

from __future__ import annotations

import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bench.harness import cx_pyperf as h

h.boot()

from bench.harness.facts import FactsRun

ERRORS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dialect", "errors")


def compile_snippet(path: str, modname: str) -> dict:
    proc = subprocess.run(
        [sys.executable, "-m", "cinderx.compiler", "--static", path,
         "--modname", modname],
        capture_output=True, text=True, timeout=180,
    )
    diagnostic, kind = "", ""
    for line in reversed(proc.stderr.splitlines()):
        if "Error:" in line:
            diagnostic = line.strip()
            kind = line.split(":", 1)[0].rsplit(".", 1)[-1]
            break
    return {
        "rejected": proc.returncode != 0,
        "exit_code": proc.returncode,
        "diagnostic": diagnostic or "(no diagnostic line found)",
        "error_kind": kind,
    }


def main() -> None:
    run = FactsRun("b_port_cost")

    if not os.path.isdir(ERRORS_DIR):
        run.unavailable(case="port_cost", note=f"missing {ERRORS_DIR}")
        run.write()
        return

    names = sorted(f[:-3] for f in os.listdir(ERRORS_DIR)
                   if f.endswith(".py") and not f.startswith("_"))
    results = []
    for name in names:
        path = os.path.join(ERRORS_DIR, f"{name}.py")
        with open(path) as fh:
            what = fh.readline().strip().lstrip("#").strip()
        res = {"snippet": name, "what": what, **compile_snippet(path, name)}
        results.append(res)
        mark = "rejected" if res["rejected"] else "COMPILED (unexpected)"
        run.log(f"  {name:<32} {mark}")
        run.log(f"      {res['diagnostic'][:120]}")
        if not res["rejected"]:
            run.unavailable(case=f"port_cost/{name}",
                            note="snippet compiled but the catalogue expects rejection")

    kinds: dict[str, int] = {}
    for r in results:
        kinds[r["error_kind"] or "none"] = kinds.get(r["error_kind"] or "none", 0) + 1

    run.record("snippets", results)
    run.record("total", len(results))
    run.record("rejected", sum(1 for r in results if r["rejected"]))
    run.record("error_kinds", kinds)
    run.write()


if __name__ == "__main__":
    main()
