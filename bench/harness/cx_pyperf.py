"""Measurement harness: a thin layer over pyperf, which does all the timing."""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import sysconfig
from collections.abc import Callable, Mapping, Sequence
from typing import Any

import pyperf

from . import system
from .system import _REEXEC_GUARD

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RESULTS = os.environ.get("BENCH_RESULTS_DIR") or os.path.join(ROOT, "results", "pyperf")

CONFIGS = ("stock", "cinderx", "static", "cinderx_jit", "static_jit")
_CONFIG_ENV = "CX_BENCH_CONFIG"

_cinderx: Any = None
_jit: Any = None
_config: str | None = None


# boot: preconditions, then the runtime


def boot(config: str | None = None, *, strict: bool | None = None) -> str:
    """First statement of every bench script."""
    global _config, _cinderx, _jit

    system.aslr_disable_and_reexec()

    if config is None:
        config = os.environ.get(_CONFIG_ENV) or "stock"
    if config not in CONFIGS:
        raise SystemExit(f"unknown config {config!r}; expected one of {CONFIGS}")
    os.environ[_CONFIG_ENV] = config
    _config = config

    if strict is None:
        strict = os.environ.get("CX_BENCH_STRICT", "") not in ("", "0")
    system.preflight(strict=strict)
    system.pin_to_isolated()

    if config == "stock":
        return config

    import cinderx
    import cinderx.jit

    _cinderx, _jit = cinderx, cinderx.jit
    cinderx.install_frame_evaluator()
    if config.startswith("static"):
        from cinderx.compiler.strict.loader import install

        install()
    if config.endswith("_jit"):
        _jit.enable()
    else:
        _jit.disable()
    return config


def config() -> str:
    if _config is None:
        raise RuntimeError("call boot() first")
    return _config


def is_static() -> bool:
    return config().startswith("static")


def jit_on() -> bool:
    return config().endswith("_jit")


def cinderx():
    return _cinderx


def jit():
    return _jit


# facts


def bench_tag() -> str:
    """Short tag identifying the running interpreter and configuration."""
    v = sys.version_info
    ft = "t" if sysconfig.get_config_var("Py_GIL_DISABLED") else ""
    impl = platform.python_implementation().lower()
    prefix = "" if impl == "cpython" else f"{impl}-"
    return f"{prefix}{v.major}{v.minor}{ft}-{_config or 'stock'}"


def machine_facts() -> dict[str, Any]:
    """Host description. pyperf's metadata does not carry the CPU model on macOS."""

    def sysctl(name: str) -> str | None:
        try:
            out = subprocess.run(["sysctl", "-n", name], capture_output=True,
                                 text=True, timeout=5)
            return out.stdout.strip() or None
        except Exception:
            return None

    info: dict[str, Any] = {"platform": platform.platform(),
                            "machine": platform.machine(),
                            "system": platform.system(),
                            "cpu_count": os.cpu_count()}
    if platform.system() == "Darwin":
        info["cpu_brand"] = sysctl("machdep.cpu.brand_string")
        info["cores_physical"] = sysctl("hw.physicalcpu")
        info["cores_perf"] = sysctl("hw.perflevel0.physicalcpu")
        info["cores_eff"] = sysctl("hw.perflevel1.physicalcpu")
        mem = sysctl("hw.memsize")
        info["mem_gb"] = round(int(mem) / 2**30, 1) if mem else None
        info["os_version"] = sysctl("kern.osproductversion")
    else:
        try:
            with open("/proc/cpuinfo") as fh:
                for line in fh:
                    if line.lower().startswith(("model name", "cpu model")):
                        info["cpu_brand"] = line.split(":", 1)[1].strip()
                        break
        except Exception:
            pass
    return info


def interp_facts() -> dict[str, Any]:
    """Interpreter and CinderX properties that are observations, not timings."""
    gil = None
    if hasattr(sys, "_is_gil_enabled"):
        try:
            gil = bool(sys._is_gil_enabled())
        except Exception:
            gil = None
    facts: dict[str, Any] = {
        "executable": sys.executable,
        "version": sys.version.split()[0],
        "implementation": platform.python_implementation(),
        "compiler": platform.python_compiler(),
        "gil_enabled": gil,
        "free_threaded": bool(sysconfig.get_config_var("Py_GIL_DISABLED")),
        "config_args": sysconfig.get_config_var("CONFIG_ARGS"),
        "core_cflags": sysconfig.get_config_var("PY_CORE_CFLAGS"),
        "lazy_imports": bool(getattr(sys.flags, "lazy_imports", False)),
        "cx_config": _config,
    }
    if _cinderx is not None:
        from importlib.metadata import version

        try:
            facts["cinderx_version"] = version("cinderx")
        except Exception:
            facts["cinderx_version"] = "unknown"
        facts["frame_evaluator"] = _cinderx.is_frame_evaluator_installed()
        facts["has_parallel_gc"] = _cinderx.has_parallel_gc()
        facts["jit_enabled"] = _jit.is_enabled()
        facts["compile_after_n_calls"] = _jit.get_compile_after_n_calls()
    return facts


def jit_snapshot() -> dict[str, Any]:
    """JIT state worth recording next to any timing taken under it."""
    if _jit is None:
        return {}
    snap: dict[str, Any] = {
        "compiled_functions": len(_jit.get_compiled_functions()),
        "compilation_time_us": _jit.get_compilation_time(),
        "allocator": _jit.get_allocator_stats(),
    }
    stats = _jit.get_and_clear_runtime_stats()
    snap["deopts"] = len(stats.get("deopt", []))
    return snap


def compile_now(*fns: Callable[..., Any], warmup: int = 0,
                run: Callable[[], Any] | None = None) -> dict[str, Any]:
    """Run `run` `warmup` times, then force_compile every fn."""
    if not jit_on():
        return {"compiled": False, "warmup": warmup}
    for _ in range(warmup):
        if run is None:
            break
        run()
    out: dict[str, Any] = {"compiled": True, "warmup": warmup, "functions": {}}
    for fn in fns:
        ok = _jit.force_compile(fn)
        out["functions"][getattr(fn, "__qualname__", repr(fn))] = {
            "force_compile": bool(ok),
            "is_jit_compiled": bool(_jit.is_jit_compiled(fn)),
            "interpreted_calls": _jit.count_interpreted_calls(fn),
            "compile_time_us": _jit.get_function_compilation_time(fn),
            "code_bytes": _jit.get_compiled_size(fn),
        }
    return out


def runtime_metrics() -> dict[str, Any]:
    """GC, allocator and memory counters; also what the workshop sampler reads."""
    import gc
    import resource

    ru = resource.getrusage(resource.RUSAGE_SELF)
    m: dict[str, Any] = {
        "gc_stats": gc.get_stats(),
        "gc_count": list(gc.get_count()),
        "gc_freeze_count": gc.get_freeze_count(),
        "gc_threshold": list(gc.get_threshold()),
        "allocated_blocks": sys.getallocatedblocks(),
        "interned_size": sys.getunicodeinternedsize(),
        "maxrss_kb": ru.ru_maxrss // (1024 if sys.platform == "darwin" else 1),
        "minflt": ru.ru_minflt, "majflt": ru.ru_majflt,
        "nvcsw": ru.ru_nvcsw, "nivcsw": ru.ru_nivcsw,
    }
    m.update(system_memory())
    return m


def system_memory() -> dict[str, int]:
    """Linux RSS and COW detail; Shared_Clean is the immortalisation probe."""
    out: dict[str, int] = {}
    try:
        with open("/proc/self/statm") as fh:
            size, rss = fh.read().split()[:2]
        page = os.sysconf("SC_PAGE_SIZE")
        out["rss_kb"] = int(rss) * page // 1024
        out["vsize_kb"] = int(size) * page // 1024
    except OSError:
        return out
    try:
        with open("/proc/self/smaps_rollup") as fh:
            for line in fh:
                key, _, rest = line.partition(":")
                if key in ("Rss", "Pss", "Shared_Clean", "Shared_Dirty",
                           "Private_Clean", "Private_Dirty"):
                    out[f"smaps_{key.lower()}_kb"] = int(rest.split()[0])
    except OSError:
        pass
    return out


# Suite


class Suite:
    """A pyperf runner plus the bookkeeping the figures, the gate and drift need."""

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
                help="tag written into the result filename and the metadata")
            self._forward = (*self._forward, "label")
        self.gate_failures: list[dict[str, Any]] = []
        self.facts: dict[str, Any] = {}
        self._registered: list[str] = []
        self._benchmarks: dict[str, Any] = {}
        self._checked: set[object] = set()
        self._parsed = False

    #: pyperf cleans the worker environment, so what a worker needs is named here.
    INHERIT_ENVIRON = ("CX_BENCH_CONFIG", "CX_BENCH_STRICT", _REEXEC_GUARD,
                       "BENCH_RESULTS_DIR")
    #: JIT tuning arrives by environment, so it has to reach the workers too.
    INHERIT_PREFIXES = ("CINDERX_",)

    #: pyperf raises its own defaults for JIT implementations (6 processes, 10
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
        jit_defaults = self._apply_jit_defaults(args)
        keep = list(args.inherit_environ or [])
        keep += [n for n in self.INHERIT_ENVIRON if n in os.environ]
        keep += [n for n in os.environ if n.startswith(self.INHERIT_PREFIXES)]
        args.inherit_environ = sorted(set(keep))
        self.label = getattr(args, "label", None) or bench_tag()
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
            self.facts["preflight"] = system.preflight()
            self.facts["jit_defaults_applied"] = jit_defaults
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

    # -- correctness ------------------------------------------------------- #

    def gate(self, *, case: str, impl: str, got: object, expected: object,
             tol: float = 0.0, note: str = "") -> bool:
        """True if `impl` may be timed. Cheap, deterministic, run everywhere."""
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
        """Verify a timed callable once per worker process, before it is timed."""
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

    # -- registration ------------------------------------------------------ #

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
        """For work that consumes or mutates its input: the rebuild is untimed."""
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
        """Whole-process timing: start-up, import latency, AOT load."""
        name = self._register(case, impl)
        self.facts.setdefault("commands", {})[name] = {
            "command": list(command), "params": params or {}, "note": note}
        b = self.runner.bench_command(name, command)
        if b is not None:
            self._benchmarks[name] = b
        return b

    def machine_probe(self) -> None:
        """A fixed workload that measures the host and not the interpreter."""
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

    # -- output ------------------------------------------------------------ #

    def drift(self) -> dict[str, Any]:
        """Monotonic-trend test over each benchmark's samples in temporal order."""
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
        """Facts, gate failures and the drift verdict. Master only."""
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


def _brief(x: object, n: int = 60) -> str:
    s = repr(x)
    return s if len(s) <= n else s[:n] + "..."


def _close(got: object, expected: object, tol: float) -> tuple[bool, float]:
    """Relative comparison; `tol` > 0 permits reassociated floating point."""
    if got == expected:
        return True, 0.0
    if isinstance(got, (int, float)) and isinstance(expected, (int, float)):
        dev = abs(got - expected) / max(1.0, abs(expected))
        return dev <= tol, dev
    if isinstance(got, (list, tuple)) and isinstance(expected, (list, tuple)):
        if len(got) != len(expected):
            return False, float("inf")
        worst = 0.0
        for a, b in zip(got, expected, strict=True):
            ok, dev = _close(a, b, tol)
            worst = max(worst, dev)
            if not ok:
                return False, worst
        return True, worst
    return False, float("inf")
