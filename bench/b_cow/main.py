from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from bench.b_cow.constants import ARMS
from bench.b_cow.run_arm import run_arm
from bench.harness import cx_pyperf as h
from bench.harness.facts import FactsRun


h.boot()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", choices=ARMS)
    ap.add_argument("--children", type=int, default=4)
    ap.add_argument("--emit-json", action="store_true",
                    help="internal: print one arm's result for the parent run")
    args = ap.parse_args()

    if not h.system_memory().get("smaps_shared_clean_kb"):
        run = FactsRun("b_cow")
        run.unsupported(case="cow",
                        note="/proc/self/smaps_rollup unavailable; Linux only")
        run.write()
        return

    if args.arm:
        result = run_arm(args.arm, args.children)
        if args.emit_json:
            print("@@RESULT@@" + json.dumps(result), flush=True)
        else:
            run = FactsRun("b_cow")
            run.record("arms", [result])
            run.write()
        return

    run = FactsRun("b_cow")
    results = []
    for arm in ARMS:
        proc = subprocess.run(
            [sys.executable, os.path.abspath(__file__), "--arm", arm,
             "--children", str(args.children), "--emit-json"],
            capture_output=True, text=True, timeout=900,
            env={**os.environ},
        )
        line = next((l for l in proc.stdout.splitlines()
                     if l.startswith("@@RESULT@@")), None)
        if line is None:
            run.unavailable(case=f"cow/{arm}", note=proc.stderr[-300:])
            continue
        res = json.loads(line[len("@@RESULT@@"):])
        results.append(res)
        shared = res.get("child_shared_clean_kb") or []
        run.log(f"  {arm:<9} child Shared_Clean = {shared} kB")
    run.record("arms", results)
    run.write()


if __name__ == "__main__":
    main()
