"""The cost of porting, measured as what the compiler refuses (plan 7.8)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from bench.b_port_cost.compile_snippet import compile_snippet
from bench.b_port_cost.constants import ERRORS_DIR
from bench.harness import cx_pyperf as h
from bench.harness.facts import FactsRun


h.boot()


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
