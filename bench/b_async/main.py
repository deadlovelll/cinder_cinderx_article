from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from bench.b_async.constants import BATCH, SUSPEND_WEIGHT, WAITERS, WEIGHTS, X
from bench.b_async.dedupe_probe import dedupe_probe
from bench.b_async.drivers import drive_await, drive_call, drive_prop, drive_ready
from bench.b_async.lazy_ready import lazy_ready
from bench.b_async.lazy_type import lazy_type
from bench.b_async.make_lazy_work import make_lazy_work
from bench.b_async.make_work import make_work
from bench.b_async.prop_ready import prop_ready
from bench.b_async.prop_type import prop_type
from bench.b_async.reference import reference
from bench.b_async.witness import witness
from bench.harness import cx_pyperf as h


h.boot()


def main() -> None:
    suite = h.Suite("b_async")
    suite.parse()

    from bench.kernels import coro_plain as cp

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    legs = []
    for w in WEIGHTS:
        legs.append(("call", f"plain/w{w}", drive_call, cp.spin, w, BATCH,
                     "one ordinary call per iteration"))
    for w in WEIGHTS:
        legs.append(("await", f"plain/w{w}", drive_await, cp.spin_coro, w, BATCH,
                     "one await of a coroutine that never suspends"))
    legs.append(("await", f"suspend/w{SUSPEND_WEIGHT}", drive_await, cp.spin_suspend,
                 SUSPEND_WEIGHT, BATCH,
                 "one await of a coroutine that yields to the loop once"))

    if h.is_static():
        from bench.kernels import coro_static as cs

        for w in WEIGHTS:
            legs.append(("await", f"static/w{w}", drive_await, cs.spin_coro, w, BATCH,
                         "one await of a typed coroutine, int64 body"))
    else:
        suite.unavailable(case="await", impl="static",
                          note="the typed coroutine needs a static config")

    jit_info: dict[str, object] = {}
    if h.jit_on():
        jit_info["drivers"] = h.compile_now(drive_call, drive_await, drive_ready,
                                            drive_prop)
        seen = []
        for _case, _impl, _driver, fn, _w, _batch, _note in legs:
            if fn not in seen:
                seen.append(fn)
        jit_info["targets"] = h.compile_now(*seen)

    witnesses: dict[str, object] = {}
    for case, impl, driver, fn, w, batch, note in legs:
        work = make_work(loop, driver, fn, X, w, batch)
        expected = reference(X, w)
        if not suite.gate(case=case, impl=impl, got=work(), expected=expected):
            continue
        witnesses[f"{case}/{impl}"] = witness(
            work, batch, {"target": fn, "driver": driver})
        suite.check_once((case, impl), work, expected)
        suite.bench(case=case, impl=impl, fn=work,
                    params={"x": X, "n": w, "batch": batch},
                    inner_loops=batch, note=note)

    lazy_cls, prop_cls = lazy_type(), prop_type()
    if lazy_cls is None or prop_cls is None:
        suite.unavailable(case="await", impl="lazy/done",
                          note="AsyncLazyValue lives in cinderx, this config has none")
        suite.unavailable(case="await", impl="prop/done",
                          note="async_cached_property lives in cinderx, "
                               "this config has none")
    else:
        # the same empty body as await/plain/w0, so the pair differs only in
        # what is being awaited: a fresh coroutine or a value already computed
        ready = [
            ("lazy/done", drive_ready, lazy_ready(loop, lazy_cls, cp.spin_coro, X, 0),
             "one await of an AsyncLazyValue that already holds its result"),
            ("prop/done", drive_prop, prop_ready(loop, prop_cls, cp.spin_coro, X, 0),
             "one await of an async_cached_property read off the instance"),
        ]
        expected = reference(X, 0)
        for impl, driver, target, note in ready:
            work = make_lazy_work(loop, driver, target, BATCH)
            if not suite.gate(case="await", impl=impl, got=work(), expected=expected):
                continue
            witnesses[f"await/{impl}"] = witness(work, BATCH, {"driver": driver})
            suite.check_once(("await", impl), work, expected)
            suite.bench(case="await", impl=impl, fn=work,
                        params={"x": X, "n": 0, "batch": BATCH}, inner_loops=BATCH,
                        note=note)
        suite.facts["lazy"] = {
            "lazy_value": f"{lazy_cls.__module__}.{lazy_cls.__qualname__}",
            "cached_property": f"{prop_cls.__module__}.{prop_cls.__qualname__}",
            "native": lazy_cls.__module__ != "cinderx._asyncio",
        }
        suite.facts["dedupe"] = dedupe_probe(loop, lazy_cls, WAITERS)

    scale_w = SUSPEND_WEIGHT
    for batch in (BATCH, 2 * BATCH):
        work = make_work(loop, drive_await, cp.spin_coro, X, scale_w, batch)
        suite.bench(case="await_scale", impl=f"plain/w{scale_w}@{batch}", fn=work,
                    params={"x": X, "n": scale_w, "batch": batch},
                    inner_loops=batch,
                    note="same cost per await at N and 2N, or the loop was folded")

    suite.machine_probe()
    suite.facts["jit"] = jit_info
    suite.facts["witness"] = witnesses
    suite.facts["jit_state"] = h.jit_snapshot()
    suite.facts["runtime_metrics"] = h.runtime_metrics()
    suite.write_sidecar()
    loop.close()


if __name__ == "__main__":
    main()
