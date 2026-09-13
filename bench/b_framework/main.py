"""What the web framework costs, and which half of it CinderX can reach."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from bench.b_framework.constants import BATCH, N_ITEMS
from bench.b_framework.have_pydantic import have_pydantic
from bench.b_framework.make_driver import make_driver
from bench.b_framework.response_of import response_of
from bench.b_framework.start_lifespan import start_lifespan
from bench.harness import cx_pyperf as h


h.boot()


HAVE_PYDANTIC = have_pydantic()


def main() -> None:
    suite = h.Suite("b_framework", forward=("leg",))
    suite.runner.argparser.add_argument(
        "--leg", default="all",
        help="one of hand|model_dict|model_instance|no_model|response_obj, or all")
    args = suite.parse()

    if not HAVE_PYDANTIC:
        suite.unavailable(case="framework", impl=h.config(),
                          note="pydantic not installed")
        suite.write_sidecar()
        return
    try:
        from bench.b_framework.build_apps import build_apps

        apps = build_apps()
    except ImportError as exc:
        suite.unavailable(case="framework", impl=h.config(),
                          note=f"fastapi not installed: {exc}")
        suite.write_sidecar()
        return

    legs = list(apps) if args.leg == "all" else [args.leg]
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    reference = None
    for name in legs:
        app = apps[name]
        start_lifespan(app, loop)
        status, body = response_of(app, loop)
        if status != 200:
            suite.gate(case="framework", impl=f"{h.config()}/{name}",
                       got=status, expected=200)
            continue
        if reference is None:
            reference = body
        if not suite.gate(case="framework", impl=f"{h.config()}/{name}",
                          got=body, expected=reference):
            continue

        work = make_driver(app, loop)
        if h.jit_on():
            h.jit().auto()
        suite.bench(case="framework", impl=f"{h.config()}/{name}", fn=work,
                    params={"leg": name, "page_items": N_ITEMS, "batch": BATCH,
                            "response_bytes": len(json.dumps(body))},
                    inner_loops=BATCH,
                    note="per request through the ASGI callable; no server, no "
                         "socket, and the event loop is entered once per batch")

    if h.jit_on():
        jit = h.jit()
        suite.facts["compiled_functions"] = len(jit.get_compiled_functions())
        stats = jit.get_and_clear_runtime_stats()
        suite.facts["deopts"] = len(stats.get("deopt", []))
        suite.facts["note_intermittent_crash"] = (
            "SIGSEGV under auto() over the framework path, reproduced twice on "
            "macOS/arm64, never under force_compile over a list; needs a core dump")

    suite.machine_probe()
    suite.write_sidecar()
    loop.close()


if __name__ == "__main__":
    main()
