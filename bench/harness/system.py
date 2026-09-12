"""Preconditions a timing is allowed to depend on, and the checks that prove them."""

from __future__ import annotations

import ctypes
import ctypes.util
import math
import os
import platform
import subprocess
import sys
from typing import Any, Sequence

ADDR_NO_RANDOMIZE = 0x0040000
_REEXEC_GUARD = "CX_BENCH_NO_ASLR"


# 1. drift: samples must not trend upward


def mann_kendall(values: Sequence[float]) -> dict[str, Any]:
    """Non-parametric monotonic-trend test."""
    n = len(values)
    if n < 8:
        return {"n": n, "verdict": "too_few_samples"}

    s = 0
    slopes = []
    for i in range(n - 1):
        vi = values[i]
        for j in range(i + 1, n):
            d = values[j] - vi
            s += (d > 0) - (d < 0)
            slopes.append(d / (j - i))

    var = n * (n - 1) * (2 * n + 5) / 18.0
    if s > 0:
        z = (s - 1) / math.sqrt(var)
    elif s < 0:
        z = (s + 1) / math.sqrt(var)
    else:
        z = 0.0
    p = 2.0 * (1.0 - _normal_cdf(abs(z)))

    slopes.sort()
    mid = len(slopes) // 2
    slope = slopes[mid] if len(slopes) % 2 else (slopes[mid - 1] + slopes[mid]) / 2.0

    first = values[: n // 2]
    second = values[-(n // 2):]
    half_ratio = (sum(second) / len(second)) / (sum(first) / len(first))

    if p >= 0.05:
        verdict = "no_trend"
    elif s > 0:
        verdict = "SLOWING"
    else:
        verdict = "speeding_up"

    return {
        "n": n, "S": s, "z": round(z, 3), "p": round(p, 5),
        "slope_per_sample": slope, "second_half_over_first": round(half_ratio, 4),
        "verdict": verdict,
    }


def _normal_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _l2_cost(values: Sequence[float]):
    """Segment cost for a mean-shift model, O(1) per query via prefix sums."""
    n = len(values)
    s = [0.0] * (n + 1)
    s2 = [0.0] * (n + 1)
    for i, v in enumerate(values):
        s[i + 1] = s[i] + v
        s2[i + 1] = s2[i] + v * v

    def cost(a: int, b: int) -> float:
        m = b - a
        if m <= 0:
            return 0.0
        total = s[b] - s[a]
        return max(0.0, (s2[b] - s2[a]) - total * total / m)

    return cost


def changepoints(values: Sequence[float], *, penalty: float | None = None,
                 min_size: int = 5) -> list[tuple[int, int]]:
    """Segment a series where the mean shifts. Returns [start, end) index pairs."""
    n = len(values)
    if n < 2 * min_size:
        return [(0, n)] if n else []
    cost = _l2_cost(values)
    if penalty is None:
        penalty = 3.0 * (cost(0, n) / n) * math.log(n)
        if penalty <= 0.0:
            return [(0, n)]

    inf = float("inf")
    f = [inf] * (n + 1)
    f[0] = -penalty  # the first segment does not pay for a split
    prev = [0] * (n + 1)
    for t in range(min_size, n + 1):
        for a in range(0, t - min_size + 1):
            if f[a] == inf:
                continue
            c = f[a] + cost(a, t) + penalty
            if c < f[t]:
                f[t] = c
                prev[t] = a
    bounds: list[tuple[int, int]] = []
    t = n
    while t > 0:
        a = prev[t]
        bounds.append((a, t))
        t = a
    bounds.reverse()
    return bounds


def classify_curve(values: Sequence[float], *, min_size: int = 5) -> dict[str, Any]:
    """Barrett et al.'s four regimes, decided from the data rather than assumed."""
    n = len(values)
    if n < 2 * min_size:
        return {"n": n, "verdict": "too_few_samples"}

    segs = changepoints(values, min_size=min_size)
    stats = []
    for a, b in segs:
        chunk = values[a:b]
        m = sum(chunk) / len(chunk)
        var = sum((x - m) ** 2 for x in chunk) / len(chunk)
        stats.append({"start": a, "end": b, "n": b - a, "mean": m,
                      "sd": math.sqrt(var)})

    final = stats[-1]
    tol = max(final["sd"], abs(final["mean"]) * 1e-3)
    best = min(stats, key=lambda s: s["mean"])

    # Does the candidate steady region actually hold still? Judged by magnitude
    tail = values[final["start"]:final["end"]]
    tail_trend = mann_kendall(tail)
    half = len(tail) // 2
    if half >= 2:
        lo = sum(tail[:half]) / half
        hi = sum(tail[-half:]) / half
        tail_drift = abs(hi - lo)
        tail_settled = tail_drift <= tol
    else:
        tail_drift, tail_settled = 0.0, True

    if not tail_settled:
        verdict = "no_steady_state"
    elif len(stats) == 1:
        verdict = "flat"
    elif final["n"] < max(min_size, n // 4):
        verdict = "no_steady_state"
    elif best["mean"] < final["mean"] - tol:
        verdict = "slowdown"
    else:
        verdict = "warmup"

    return {
        "n": n, "segments": stats, "n_segments": len(stats),
        "final_mean": final["mean"], "best_mean": best["mean"],
        "best_segment_index": stats.index(best),
        "steady_from": final["start"],
        "final_over_best": (final["mean"] / best["mean"]) if best["mean"] else None,
        "tolerance": tol, "final_segment_trend": tail_trend,
        "final_segment_drift": tail_drift, "final_segment_settled": tail_settled,
        "verdict": verdict,
    }


def drift_report(named_values: dict[str, Sequence[float]]) -> dict[str, Any]:
    """Run the trend test over every benchmark's samples in temporal order."""
    per_bench = {name: mann_kendall(vals) for name, vals in named_values.items()}
    slowing = sorted(n for n, r in per_bench.items() if r.get("verdict") == "SLOWING")
    return {
        "test": "mann_kendall",
        "alpha": 0.05,
        "benchmarks": per_bench,
        "slowing": slowing,
        "verdict": "DRIFT" if slowing else "ok",
    }


# 2. ASLR off


def aslr_disable_and_reexec(argv: list[str] | None = None) -> None:
    """Ask the kernel to stop randomising, then re-exec so it takes effect."""
    if os.environ.get(_REEXEC_GUARD) == "1":
        return
    if platform.system() != "Linux":
        os.environ[_REEXEC_GUARD] = "unsupported"
        return
    libc_name = ctypes.util.find_library("c")
    if not libc_name:
        os.environ[_REEXEC_GUARD] = "no_libc"
        return
    try:
        libc = ctypes.CDLL(libc_name, use_errno=True)
        libc.personality.argtypes = [ctypes.c_ulong]
        libc.personality.restype = ctypes.c_int
        if libc.personality(ADDR_NO_RANDOMIZE) < 0:
            os.environ[_REEXEC_GUARD] = f"errno={ctypes.get_errno()}"
            return
    except Exception as exc:  # pragma: no cover - platform dependent
        os.environ[_REEXEC_GUARD] = f"failed:{type(exc).__name__}"
        return
    os.environ[_REEXEC_GUARD] = "1"
    args = argv if argv is not None else [sys.executable, *sys.argv]
    os.execv(args[0], args)


def aslr_facts() -> dict[str, Any]:
    """What the kernel says, and what two child processes actually do."""
    facts: dict[str, Any] = {"reexec": os.environ.get(_REEXEC_GUARD, "not_attempted")}

    try:
        with open("/proc/self/personality") as fh:
            value = int(fh.read().strip(), 16)
        facts["personality"] = hex(value)
        facts["addr_no_randomize"] = bool(value & ADDR_NO_RANDOMIZE)
    except OSError:
        facts["personality"] = None
        facts["addr_no_randomize"] = None

    try:
        with open("/proc/sys/kernel/randomize_va_space") as fh:
            facts["randomize_va_space"] = int(fh.read().strip())
    except OSError:
        facts["randomize_va_space"] = None

    facts.update(_aslr_empirical())
    if facts.get("layout_stable") is True:
        facts["verdict"] = "off"
    elif facts.get("layout_stable") is False:
        facts["verdict"] = "ON"
    else:
        facts["verdict"] = "unknown"
    return facts


def _aslr_empirical(trials: int = 3) -> dict[str, Any]:
    """The check that cannot be fooled: does a child map itself at the same place?"""
    probe = (
        "import sys;"
        "print([l.split('-')[0] for l in open('/proc/self/maps')"
        " if l.rstrip().endswith('[stack]') or ' r-xp ' in l][:1][0])"
    )
    seen = []
    for _ in range(trials):
        try:
            out = subprocess.run([sys.executable, "-c", probe],
                                 capture_output=True, text=True, timeout=30)
        except Exception:
            return {"layout_stable": None, "layout_samples": []}
        if out.returncode != 0:
            return {"layout_stable": None, "layout_samples": []}
        seen.append(out.stdout.strip())
    return {"layout_stable": len(set(seen)) == 1, "layout_samples": seen}


# 3. a core of one's own


def _read(path: str) -> str | None:
    try:
        with open(path) as fh:
            return fh.read().strip()
    except OSError:
        return None


def parse_cpu_list(text: str | None) -> list[int]:
    """Parse the kernel's "0-3,7" CPU list syntax."""
    if not text:
        return []
    out: list[int] = []
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            lo, hi = part.split("-", 1)
            out.extend(range(int(lo), int(hi) + 1))
        else:
            out.append(int(part))
    return sorted(set(out))


def cpu_facts() -> dict[str, Any]:
    """Isolation, affinity, governor and turbo, with a verdict on reservation."""
    facts: dict[str, Any] = {"cpu_count": os.cpu_count()}
    if platform.system() != "Linux":
        facts["verdict"] = "unsupported"
        facts["reason"] = "CPU isolation is a Linux kernel feature"
        return facts

    isolated = parse_cpu_list(_read("/sys/devices/system/cpu/isolated"))
    nohz = parse_cpu_list(_read("/sys/devices/system/cpu/nohz_full"))
    facts["isolated"] = isolated
    facts["nohz_full"] = nohz
    facts["cmdline"] = _read("/proc/cmdline")

    try:
        facts["affinity"] = sorted(os.sched_getaffinity(0))
    except (AttributeError, OSError):
        facts["affinity"] = None

    governors, boost = {}, None
    for cpu in range(os.cpu_count() or 0):
        g = _read(f"/sys/devices/system/cpu/cpu{cpu}/cpufreq/scaling_governor")
        if g:
            governors[cpu] = g
    facts["governors"] = sorted(set(governors.values())) or None
    no_turbo = _read("/sys/devices/system/cpu/intel_pstate/no_turbo")
    if no_turbo is not None:
        boost = no_turbo == "1"
    else:
        cpufreq_boost = _read("/sys/devices/system/cpu/cpufreq/boost")
        if cpufreq_boost is not None:
            boost = cpufreq_boost == "0"
    facts["turbo_disabled"] = boost

    smt = _read("/sys/devices/system/cpu/smt/control")
    facts["smt"] = smt

    problems = []
    if not isolated:
        problems.append("no isolcpus= CPUs: nothing is reserved")
    elif facts["affinity"] and not set(facts["affinity"]) <= set(isolated):
        problems.append("process affinity is not confined to the isolated CPUs")
    if isolated and not set(isolated) <= set(nohz):
        problems.append("isolated CPUs are not all in nohz_full")
    if facts["governors"] and facts["governors"] != ["performance"]:
        problems.append(f"governor is {facts['governors']}, not performance")
    if boost is False:
        problems.append("turbo is enabled")

    facts["problems"] = problems
    facts["verdict"] = "reserved" if not problems else "NOT_RESERVED"
    return facts


def pin_to_isolated() -> dict[str, Any]:
    """Confine this process to the isolated CPUs, if there are any."""
    facts = cpu_facts()
    isolated = facts.get("isolated") or []
    if not isolated or not hasattr(os, "sched_setaffinity"):
        return {"pinned": False, **facts}
    try:
        os.sched_setaffinity(0, set(isolated))
        return {"pinned": True, "affinity": sorted(os.sched_getaffinity(0)), **facts}
    except OSError as exc:
        return {"pinned": False, "error": str(exc), **facts}


# all three at once


def preflight(*, strict: bool = False) -> dict[str, Any]:
    """Gather all preconditions. With strict=True, refuse to run a bad host."""
    facts = {"aslr": aslr_facts(), "cpu": cpu_facts()}
    bad = [
        f"aslr={facts['aslr']['verdict']}" if facts["aslr"]["verdict"] != "off" else None,
        f"cpu={facts['cpu']['verdict']}" if facts["cpu"]["verdict"] != "reserved" else None,
    ]
    facts["problems"] = [b for b in bad if b]
    facts["verdict"] = "ok" if not facts["problems"] else "DEGRADED"
    if strict and facts["problems"]:
        raise SystemExit(
            "refusing to measure on this host: " + ", ".join(facts["problems"])
            + "\nsee bench/harness/system.py and "
              "https://pyperf.readthedocs.io/en/latest/system.html"
        )
    return facts


def describe(facts: dict[str, Any]) -> str:
    a, c = facts["aslr"], facts["cpu"]
    lines = [f"preflight: {facts['verdict']}"]
    lines.append(f"  aslr      {a['verdict']:<14} personality={a.get('personality')} "
                 f"randomize_va_space={a.get('randomize_va_space')} "
                 f"layout_stable={a.get('layout_stable')}")
    lines.append(f"  cpu       {c['verdict']:<14} isolated={c.get('isolated')} "
                 f"affinity={c.get('affinity')} governor={c.get('governors')} "
                 f"turbo_disabled={c.get('turbo_disabled')}")
    for p in c.get("problems", []):
        lines.append(f"            - {p}")
    return "\n".join(lines)


if __name__ == "__main__":
    aslr_disable_and_reexec()
    print(describe(preflight()))
