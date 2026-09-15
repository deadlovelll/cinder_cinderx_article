from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from bench.b_install_order.constants import COMBOS
from bench.b_install_order.run_combo import run_combo


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--combo", choices=COMBOS)
    ap.add_argument("--emit-json", action="store_true")
    args = ap.parse_args()

    if args.combo:
        res = run_combo(args.combo)
        if args.emit_json:
            print("@@RESULT@@" + json.dumps(res), flush=True)
        return

    from bench.harness import cx_pyperf as h

    h.boot("stock")
    from bench.harness.facts import FactsRun

    run = FactsRun("b_install_order")
    results = []
    for combo in COMBOS:
        proc = subprocess.run(
            [sys.executable, os.path.abspath(__file__), "--combo", combo,
             "--emit-json"],
            capture_output=True, text=True, timeout=600, env={**os.environ},
        )
        line = next((l for l in proc.stdout.splitlines()
                     if l.startswith("@@RESULT@@")), None)
        if line is None:
            run.unavailable(case=f"install_order/{combo}", note=proc.stderr[-300:])
            continue
        res = json.loads(line[len("@@RESULT@@"):])
        results.append(res)
        run.log(f"  {combo:<10} evaluator={str(res['frame_evaluator']):<5} "
                f"loader={str(res['loader']):<5} "
                f"is_static_module={str(res['is_static_module']):<5} "
                f"{res['median_ms']:8.1f} ms")
    run.record("combos", results)
    run.write()


if __name__ == "__main__":
    main()
