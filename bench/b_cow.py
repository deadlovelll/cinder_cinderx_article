"""Copy-on-write after fork, with and without immortalisation (plan 7.13)."""

from __future__ import annotations

import argparse
import gc
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bench.harness import cx_pyperf as h

h.boot()

from bench.harness.facts import FactsRun

N_OBJECTS = 400_000
TOUCH_PASSES = 3
ARMS = ("plain", "frozen", "immortal")


def build(n: int) -> list:
    """The kind of heap a preloaded application holds before it forks."""
    return [{"id": i, "name": f"item-{i}", "tags": (i % 7, i % 11)} for i in range(n)]


def touch(heap: list, passes: int) -> int:
    """Read-only traversal: no mutation, only refcount traffic."""
    total = 0
    for _ in range(passes):
        for obj in heap:
            total += obj["id"] + len(obj["name"])
    return total


def run_arm(arm: str, n_children: int) -> dict:
    heap = build(N_OBJECTS)
    gc.collect()

    if arm == "frozen":
        gc.freeze()
    elif arm == "immortal":
        cx = h.cinderx()
        if cx is None:
            return {"arm": arm, "status": "skipped", "note": "needs a cinderx config"}
        cx.immortalize_heap()

    before = h.system_memory()
    kids = []
    for w in range(n_children):
        r, wfd = os.pipe()
        pid = os.fork()
        if pid == 0:
            os.close(r)
            try:
                touch(heap, TOUCH_PASSES)
                payload = json.dumps({"worker": w, **h.system_memory()}).encode()
                os.write(wfd, payload)
            finally:
                os._exit(0)
        os.close(wfd)
        kids.append((pid, r))

    children = []
    for pid, r in kids:
        chunks = []
        while True:
            b = os.read(r, 65536)
            if not b:
                break
            chunks.append(b)
        os.close(r)
        os.waitpid(pid, 0)
        if chunks:
            children.append(json.loads(b"".join(chunks)))

    return {
        "arm": arm, "status": "ok", "objects": N_OBJECTS,
        "touch_passes": TOUCH_PASSES, "parent_before_fork": before,
        "children": children,
        "child_shared_clean_kb": [c.get("smaps_shared_clean_kb") for c in children],
    }


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

    # no arm given: each arm needs a fresh process, so drive them
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
