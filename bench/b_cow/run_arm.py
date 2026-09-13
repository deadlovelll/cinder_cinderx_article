from __future__ import annotations

import gc
import json
import os

from bench.b_cow.build import build
from bench.b_cow.constants import N_OBJECTS, TOUCH_PASSES
from bench.b_cow.touch import touch
from bench.harness import cx_pyperf as h


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
