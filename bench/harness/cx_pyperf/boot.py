from __future__ import annotations

import os
import sys

from bench.harness import system
from bench.harness.cx_pyperf import state
from bench.harness.cx_pyperf.constants import CONFIGS, _CONFIG_ENV


def boot(config: str | None = None, *, strict: bool | None = None,
         pin: str = "service") -> str:
    """First statement of every bench script. pin: "service" or "threads"."""

    system.aslr_disable_and_reexec()

    if config is None:
        config = os.environ.get(_CONFIG_ENV) or "stock"
    if config not in CONFIGS:
        raise SystemExit(f"unknown config {config!r}; expected one of {CONFIGS}")
    os.environ[_CONFIG_ENV] = config
    state.config = config
    want = None if pin == "service" else system.cpu_budget().get(pin)
    state.pin = system.pin_to_reserved(want)
    state.pin["pin_target"] = pin
    state.pin_expect = want
    if state.pin.get("pin_source") and not state.pin["pinned"]:
        print(f"pin: FAILED ({state.pin.get('error') or state.pin.get('affinity')})",
              file=sys.stderr, flush=True)

    if strict is None:
        strict = os.environ.get("CX_BENCH_STRICT", "") not in ("", "0")
    system.preflight(strict=strict, expect=want)

    if config == "stock":
        return config

    import cinderx
    import cinderx.jit

    state.cinderx, state.jit = cinderx, cinderx.jit
    cinderx.install_frame_evaluator()
    if config.startswith("static"):
        from cinderx.compiler.strict.loader import install

        install()
    if config.endswith("_jit"):
        state.jit.enable()
    else:
        state.jit.disable()
    return config
