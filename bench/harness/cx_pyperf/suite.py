from __future__ import annotations

import json
import os
import sys
from collections.abc import Callable, Mapping, Sequence
from typing import Any

import pyperf

from bench.harness import system
from bench.harness.cx_pyperf import state
from bench.harness.cx_pyperf.bench_tag import bench_tag
from bench.harness.cx_pyperf.brief import _brief
from bench.harness.cx_pyperf.close import _close
from bench.harness.cx_pyperf.config import config
from bench.harness.cx_pyperf.constants import RESULTS
from bench.harness.cx_pyperf.interp_facts import interp_facts
from bench.harness.cx_pyperf.jit_on import jit_on
from bench.harness.cx_pyperf.machine_facts import machine_facts
from bench.harness.system import RESERVED_ENV, _REEXEC_GUARD


class Suite:

    def __init__(self, name: str, *, forward: Sequence[str] = (),
                 label_arg: bool = True) -> None:
        self.name = name
        self._forward = tuple(forward)

        def add_cmdline_args(cmd: list[str], args: Any) -> None:
            for opt in self._forward:
                val = getattr(args, opt.replace("-", "_"), None)
                if val is None or val is False:
                    continue
                if val is True:
                    cmd.append(f"--{opt}")
                else:
                    cmd.extend([f"--{opt}", str(val)])

        self.runner = pyperf.Runner(add_cmdline_args=add_cmdline_args)
        if label_arg:
            self.runner.argparser.add_argument(
                "--label", default=None,
                help="parameter tag appended to the result filename, so that "
                     "invocations that differ only by argument do not "
                     "overwrite each other")
            self._forward = (*self._forward, "label")
        self.gate_failures: list[dict[str, Any]] = []
        self.facts: dict[str, Any] = {}
        self._registered: list[str] = []
        self._benchmarks: dict[str, Any] = {}
        self._checked: set[object] = set()
        self._parsed = False

    INHERIT_ENVIRON = ("CX_BENCH_CONFIG", "CX_BENCH_STRICT", "CX_BENCH_CPUS",
                       RESERVED_ENV, _REEXEC_GUARD, "BENCH_RESULTS_DIR")
    INHERIT_PREFIXES = ("CINDERX_",)

    JIT_DEFAULTS = {"processes": 6, "values": 10, "warmups": 10}

    def _apply_jit_defaults(self, args: Any) -> dict[str, Any]:
        if not jit_on():
            return {}
        flags = {"processes": ("-p", "--processes"), "values": ("-n", "--values"),
                 "warmups": ("-w", "--warmups")}
        given = {
            name for name, opts in flags.items()
            if any(a == o or a.startswith(o + "=") for a in sys.argv[1:] for o in opts)
        }
        applied = {}
        for name, value in self.JIT_DEFAULTS.items():
            if name in given or not hasattr(args, name):
                continue
            setattr(args, name, value)
            applied[name] = value
        return applied

    def parse(self) -> Any:
        args = self.runner.parse_args()
        if state.pin_expect and not args.affinity:
            args.affinity = system.format_cpu_list(sorted(state.pin_expect))
        jit_defaults = self._apply_jit_defaults(args)
        keep = list(args.inherit_environ or [])
        keep += [n for n in self.INHERIT_ENVIRON if n in os.environ]
        keep += [n for n in os.environ if n.startswith(self.INHERIT_PREFIXES)]
        args.inherit_environ = sorted(set(keep))
        given = getattr(args, "label", None)
        self.label = f"{bench_tag()}-{given}" if given else bench_tag()
        if not args.worker:
            os.makedirs(RESULTS, exist_ok=True)
            if not args.output and not getattr(args, "append", None):
                args.output = os.path.join(RESULTS, f"{self.name}-{self.label}.json")
                if os.path.exists(args.output):
                    os.remove(args.output)
        self.runner.metadata["mp_suite"] = self.name
        self.runner.metadata["mp_label"] = self.label
        self.runner.metadata["cx_config"] = config()
        self._parsed = True
        if self.is_master:
            self.facts["preflight"] = system.preflight(expect=state.pin_expect)
            self.facts["jit_defaults_applied"] = jit_defaults
            self.facts["pin"] = state.pin
            print(system.describe(self.facts["preflight"]), flush=True)
            if jit_defaults:
                print(f"  jit       defaults applied {jit_defaults} "
                      f"(pyperf sees cpython, not a JIT)", flush=True)
        return args

    @property
    def is_master(self) -> bool:
        args = self.runner.args
        assert args is not None, "call parse() first"
        return not args.worker

    def log(self, msg: str) -> None:
        if self.is_master:
            print(msg, flush=True)


    def gate(self, *, case: str, impl: str, got: object, expected: object,
             tol: float = 0.0, note: str = "") -> bool:
        ok, dev = _close(got, expected, tol)
        if not ok:
            self.gate_failures.append({
                "case": case, "impl": impl, "status": "wrong_result",
                "got": _brief(got), "expected": _brief(expected),
                "deviation": dev, "tol": tol, "note": note,
            })
            self.log(f"  GATE FAIL {case:<24} {impl:<22} got={_brief(got)} "
                     f"expected={_brief(expected)} dev={dev:.2e}")
        return ok

    def unavailable(self, *, case: str, impl: str, note: str) -> None:
        self.gate_failures.append({"case": case, "impl": impl,
                                   "status": "unavailable", "note": note[:300]})
        self.log(f"  UNAVAILABLE {case:<22} {impl:<22} {note[:80]}")

    def check_once(self, key: object, verify: Callable[[], object],
                   expected: object, tol: float = 0.0) -> None:
        if key in self._checked:
            return
        self._checked.add(key)
        got = verify()
        ok, dev = _close(got, expected, tol)
        if not ok:
            raise RuntimeError(
                f"correctness check failed in this process for {key}: "
                f"got {_brief(got)}, expected {_brief(expected)}, "
                f"relative deviation {dev:.3e} > tol {tol:.3e}")


    def _md(self, case: str, impl: str, params: Mapping[str, Any] | None,
            note: str) -> dict[str, str]:
        md = {"mp_case": case, "mp_impl": impl, "cx_config": config()}
        if params:
            md["mp_params"] = json.dumps(params, sort_keys=True, separators=(",", ":"))
        if note:
            md["mp_note"] = note[:200]
        return md

    def _register(self, case: str, impl: str) -> str:
        assert self._parsed, "call parse() first"
        name = f"{case}/{impl}"
        assert name not in self._registered, f"duplicate benchmark {name}"
        self._registered.append(name)
        return name

    def bench(self, *, case: str, impl: str, fn: Callable[[], object],
              params: Mapping[str, Any] | None = None, note: str = "",
              inner_loops: int | None = None) -> Any:
        name = self._register(case, impl)
        b = self.runner.bench_func(name, fn, metadata=self._md(case, impl, params, note),
                                   inner_loops=inner_loops)
        if b is not None:
            self._benchmarks[name] = b
        return b

    def bench_time(self, *, case: str, impl: str,
                   time_fn: Callable[[int], float],
                   params: Mapping[str, Any] | None = None, note: str = "",
                   inner_loops: int | None = None) -> Any:
        name = self._register(case, impl)
        b = self.runner.bench_time_func(name, time_fn,
                                        metadata=self._md(case, impl, params, note),
                                        inner_loops=inner_loops)
        if b is not None:
            self._benchmarks[name] = b
        return b

    def bench_command(self, *, case: str, impl: str, command: Sequence[str],
                      params: Mapping[str, Any] | None = None,
                      note: str = "") -> Any:
        name = self._register(case, impl)
        self.facts.setdefault("commands", {})[name] = {
            "command": list(command), "params": params or {}, "note": note}
        b = self.runner.bench_command(name, command)
        if b is not None:
            self._benchmarks[name] = b
        return b

    def machine_probe(self) -> None:
        base, exp, mod = (1 << 2047) | 12345, 20_000, (1 << 2048) - 173
        self.bench(case="machine_probe", impl="modexp",
                   fn=lambda: pow(base, exp, mod),
                   params={"bits": 2048, "exp": exp},
                   note="big-int modexp in C; general ALU; JIT cannot touch it")

        import hashlib

        buf = bytes(range(256)) * (16 * 4096)
        self.bench(case="machine_probe", impl="digest",
                   fn=lambda: hashlib.sha256(buf).digest(),
                   params={"bytes": len(buf)},
                   note="sha256 in C; may use hardware crypto, so steadier")


    def drift(self) -> dict[str, Any]:
        values = {}
        for name, b in self._benchmarks.items():
            try:
                values[name] = list(b.get_values())
            except Exception:
                continue
        if not values:
            return {"verdict": "no_samples"}
        return system.drift_report(values)

    def write_sidecar(self) -> None:
        if not self.is_master:
            return
        os.makedirs(RESULTS, exist_ok=True)
        path = os.path.join(RESULTS, f"{self.name}-{self.label}.facts.json")
        drift = self.drift()
        payload = {
            "suite": self.name,
            "label": self.label,
            "cx_config": config(),
            "interp": interp_facts(),
            "machine": machine_facts(),
            "preflight": self.facts.get("preflight"),
            "drift": drift,
            "registered": self._registered,
            "gate_failures": self.gate_failures,
            "facts": {k: v for k, v in self.facts.items() if k != "preflight"},
        }
        with open(path, "w") as fh:
            json.dump(payload, fh, indent=1, default=str)
        print(f"[{self.name}] sidecar -> {path}", flush=True)
        if drift.get("verdict") == "DRIFT":
            print(f"[{self.name}] DRIFT: samples trend upward in "
                  f"{', '.join(drift['slowing'])} -- this run is not comparable",
                  file=sys.stderr, flush=True)
