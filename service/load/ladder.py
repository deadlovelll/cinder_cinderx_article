
from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


@dataclass(slots=True)
class Rung:

    name: str
    env: dict[str, str]
    expect: dict[str, object] = field(default_factory=dict)
    image: str | None = None
    note: str = ""


def ladder(dep_extra: str) -> list[Rung]:
    base = {"RECSYS_DEP_EXTRA": dep_extra}

    def env(**kw: str) -> dict[str, str]:
        return {**base, **{k: str(v) for k, v in kw.items()}}

    return [
        Rung("01_stock", env(RECSYS_CINDERX_MODE="off"),
             expect={"bootstrap.mode": "off", "bootstrap.frame_evaluator": False,
                     "bootstrap.cpython_jit": False},
             image="stock-3.14",
             note="stock CPython: the baseline every other rung is read against"),
        Rung("02_stock_tier2", env(RECSYS_CINDERX_MODE="off"),
             expect={"bootstrap.mode": "off", "bootstrap.frame_evaluator": False,
                     "bootstrap.cpython_jit": True},
             image="python-3.14-jit",
             note="CPython's own copy-and-patch JIT: the reader's real alternative"),
        Rung("03_fork", env(RECSYS_CINDERX_MODE="off"),
             expect={"bootstrap.mode": "off", "bootstrap.frame_evaluator": False},
             image="meta-3.14",
             note="the meta fork without the extension: isolates the fork itself"),
        Rung("04_runtime", env(RECSYS_CINDERX_MODE="runtime"),
             expect={"bootstrap.frame_evaluator": True,
                     "bootstrap.jit_enabled": False},
             image="meta-3.14",
             note="CinderX interpreter, JIT off: what the runtime costs by itself"),
        Rung("05_jit", env(RECSYS_CINDERX_MODE="jit"),
             expect={"bootstrap.jit_enabled": True},
             image="meta-3.14",
             note="JIT on, nothing precompiled: what auto() gives an application"),
        Rung("06_jit_precompiled", env(RECSYS_CINDERX_MODE="jit", RECSYS_PRECOMPILE=1),
             expect={"bootstrap.jit_enabled": True, "bootstrap.precompiled_gt": 0},
             image="meta-3.14",
             note="precompiled before the fork: the compiler's ceiling. auto()'s "
                  "threshold is 1000 calls, so 05 and 06 are different programs"),
        Rung("07_lazy_imports", env(RECSYS_CINDERX_MODE="jit", RECSYS_PRECOMPILE=1),
             image="meta-3.14",
             note="lazy imports: fork-only, so this rung needs rung 03's image"),
        Rung("08_immortalized",
             env(RECSYS_CINDERX_MODE="jit", RECSYS_PRECOMPILE=1, RECSYS_IMMORTALIZE=1),
             expect={"bootstrap.immortalized": True},
             image="meta-3.14",
             note="immortalize_heap() before the fork: refcounts stop moving"),
        Rung("09_parallel_gc",
             env(RECSYS_CINDERX_MODE="jit", RECSYS_PRECOMPILE=1, RECSYS_IMMORTALIZE=1,
                 RECSYS_PARALLEL_GC=1),
             expect={"bootstrap.parallel_gc": True},
             image="meta-3.14",
             note="parallel collector, only after 08: before it, a measured loss"),
        Rung("10_static_kernel_nojit",
             env(RECSYS_CINDERX_MODE="runtime", RECSYS_KERNEL="static"),
             expect={"bootstrap.kernel_is_static": True,
                     "bootstrap.jit_enabled": False},
             image="meta-3.14",
             note="Static Python without the JIT: the rung that answers whether "
                  "types pay on their own"),
        Rung("11_static_kernel",
             env(RECSYS_CINDERX_MODE="jit_static", RECSYS_KERNEL="static",
                 RECSYS_PRECOMPILE=1, RECSYS_IMMORTALIZE=1),
             expect={"bootstrap.kernel_is_static": True,
                     "bootstrap.jit_enabled": True},
             image="meta-3.14",
             note="Static Python plus the JIT: the two halves together"),
        Rung("12_static_embeddings",
             env(RECSYS_CINDERX_MODE="jit_static", RECSYS_KERNEL="static",
                 RECSYS_PRECOMPILE=1, RECSYS_IMMORTALIZE=1,
                 RECSYS_EMBEDDINGS="static"),
             expect={"bootstrap.kernel_is_static": True,
                     "bootstrap.jit_enabled": True,
                     "bootstrap.embeddings_is_static": True},
             image="meta-3.14",
             note="the similarity scan typed as well. Every rung up to here "
                  "leaves it in numpy, so this is the one rung where the types "
                  "replace C rather than dynamic Python"),
    ]


def fetch_health(url: str, timeout: float = 3.0) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read())


def wait_healthy(url: str, deadline_s: float) -> dict | None:
    end = time.monotonic() + deadline_s
    last: Exception | None = None
    while time.monotonic() < end:
        try:
            return fetch_health(url)
        except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
            last = exc
            time.sleep(1.0)
    print(f"  service never became healthy: {last}", file=sys.stderr)
    return None


def parse_rates(spec: str, endpoints: list[str]) -> dict[str, str]:
    if "=" not in spec:
        return {e: spec for e in endpoints}
    groups: dict[str, str] = {}
    for part in spec.split(";"):
        part = part.strip()
        if not part:
            continue
        name, _, rates = part.partition("=")
        groups[name.strip()] = rates.strip()
    fallback = groups.get("*") or next(iter(groups.values()))
    missing = [e for e in endpoints if e not in groups and "*" not in groups]
    if missing:
        print(f"  rates: {', '.join(missing)} not named in --rates, "
              f"using {fallback}", file=sys.stderr)
    return {e: groups.get(e, fallback) for e in endpoints}


def quiesce(url: str, budget_s: float, settle_s: float = 3.0) -> dict:
    deadline = time.monotonic() + budget_s
    started = time.monotonic()
    quiet_since: float | None = None
    slowest = 0.0
    while time.monotonic() < deadline:
        t0 = time.monotonic()
        try:
            fetch_health(url, timeout=5.0)
            took = time.monotonic() - t0
        except (urllib.error.URLError, OSError, json.JSONDecodeError):
            took = 5.0
        slowest = max(slowest, took)
        if took < 0.25:
            quiet_since = quiet_since or time.monotonic()
            if time.monotonic() - quiet_since >= settle_s:
                return {"waited_s": round(time.monotonic() - started, 1),
                        "settled": True, "slowest_probe_s": round(slowest, 2)}
        else:
            quiet_since = None
        time.sleep(0.5)
    return {"waited_s": round(time.monotonic() - started, 1),
            "settled": False, "slowest_probe_s": round(slowest, 2)}


def ramp_validity(verdict: dict) -> tuple[bool, str]:
    steps = verdict.get("steps") or []
    if not steps:
        return False, "the verdict carries no steps"
    first = steps[0]
    floor = (verdict.get("criterion") or {}).get("throughput_floor", 0.95)
    delivered = first.get("delivered_share") or 0.0
    if delivered < floor:
        return False, (f"the lowest rate ({first['rate']} rps) delivered only "
                       f"{delivered * 100:.1f}%, below the {floor * 100:.0f}% floor")
    return True, ""


def _dig(payload: dict, path: str):
    node: object = payload
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def verify(health: dict, expect: dict[str, object]) -> list[str]:
    problems = []
    for key, want in expect.items():
        if key.endswith("_gt"):
            got = _dig(health, key[:-3])
            if not isinstance(got, int) or got <= want:
                problems.append(f"{key[:-3]}={got!r}, expected > {want!r}")
            continue
        got = _dig(health, key)
        if got != want:
            problems.append(f"{key}={got!r}, expected {want!r}")
    reported = _dig(health, "bootstrap.problems") or []
    problems.extend(f"runtime reported: {p}" for p in reported)
    return problems


_warned_no_taskset = False


def on_cpus(cpus: str) -> list[str]:
    global _warned_no_taskset
    if not cpus:
        return []
    if not shutil.which("taskset"):
        if not _warned_no_taskset:
            print("  taskset is absent: CPU sets requested but not enforced",
                  file=sys.stderr)
            _warned_no_taskset = True
        return []
    return ["taskset", "-c", cpus]


def reset_fixture(rung: Rung, args) -> dict | None:
    if args.no_fixture_reset:
        return None
    env = {**os.environ, "RECSYS_DB_HOST": args.db_host,
           "PYTHONPATH": str(ROOT / "src")}
    proc = subprocess.run([*on_cpus(args.load_cpus), args.python,
                           str(HERE / "reset_fixture.py"), "--reset"],
                          cwd=ROOT, env=env, capture_output=True, text=True)
    if proc.returncode != 0:
        print(f"  fixture reset failed: {proc.stderr[-300:]}", file=sys.stderr)
        return {"ok": False, "stderr": proc.stderr[-300:]}
    return {"ok": True, "report": proc.stdout.strip()}


def start_service(rung: Rung, args) -> subprocess.Popen:
    env = {**os.environ, **rung.env,
           "RECSYS_DB_HOST": args.db_host,
           "RECSYS_WORKERS": str(args.workers),
           "RECSYS_SAMPLER_DIR": str(Path(args.out) / rung.name / "sampler")}
    Path(env["RECSYS_SAMPLER_DIR"]).mkdir(parents=True, exist_ok=True)
    cmd = [*on_cpus(args.service_cpus), args.python, "-m", "gunicorn",
           "-c", str(ROOT / "gunicorn_conf.py"),
           "-b", f"127.0.0.1:{args.port}", "recsys.api.app:app"]
    log = open(Path(args.out) / rung.name / "service.log", "w")
    return subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=log, stderr=log,
                            start_new_session=True)


def stop_service(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    try:
        proc.wait(timeout=30)
    except subprocess.TimeoutExpired:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        proc.wait(timeout=10)


def run_ramp(rung: Rung, endpoint: str, args, attempt: int) -> dict | None:
    tag = f"{rung.name}-a{attempt}"
    out_dir = Path(args.out) / rung.name
    env = {
        **os.environ,
        "BASE_URL": f"http://127.0.0.1:{args.port}",
        "ENDPOINT": endpoint,
        "RATES": args.rates_by_endpoint[endpoint],
        "MAX_VUS": str(args.max_vus),
        "STEP_SECONDS": str(args.step_seconds),
        "DRAIN_SECONDS": str(args.drain_seconds),
        "WARMUP_SECONDS": str(args.warmup_seconds),
        "WARMUP_RATE": str(args.warmup_rate),
        "P99_BUDGET_MS": str(args.p99_budget_ms),
        "N_USERS": str(args.n_users),
        "N_ITEMS": str(args.n_items),
        "OUT_DIR": str(out_dir),
        "RUN_TAG": tag,
    }
    proc = subprocess.run([*on_cpus(args.load_cpus), args.k6, "run", "--quiet",
                           str(HERE / "ramp.js")],
                          cwd=ROOT, env=env, capture_output=True, text=True)
    sys.stdout.write(proc.stdout)
    path = out_dir / f"{tag}-{endpoint}.json"
    if not path.exists():
        print(f"  k6 produced no verdict for {endpoint}: {proc.stderr[-400:]}",
              file=sys.stderr)
        return None
    return json.loads(path.read_text())


def run_rung(rung: Rung, args, attempt: int) -> dict:
    record: dict[str, object] = {
        "rung": rung.name, "attempt": attempt, "note": rung.note,
        "env": rung.env, "started_at": datetime.now(UTC).isoformat(),
        "image": rung.image, "python": args.python,
    }
    (Path(args.out) / rung.name).mkdir(parents=True, exist_ok=True)

    if rung.image and rung.image not in args.available_images:
        record["status"] = "skipped"
        record["reason"] = (f"needs interpreter image {rung.image!r}, which is not "
                            f"available; environment variables cannot make this rung")
        print(f"  SKIP {rung.name}: {record['reason']}")
        return record

    reset = reset_fixture(rung, args)
    if reset is not None:
        record["fixture_reset"] = reset
        if not reset["ok"]:
            record["status"] = "failed"
            record["reason"] = ("could not reset the fixture; a rung measured on a "
                                "burned-in fixture is not comparable with the others")
            return record

    proc = start_service(rung, args)
    try:
        health = wait_healthy(f"http://127.0.0.1:{args.port}/healthz", args.boot_timeout)
        if health is None:
            record["status"] = "failed"
            record["reason"] = "service did not become healthy"
            return record

        record["health"] = health
        problems = verify(health, rung.expect)
        if problems:
            record["status"] = "mismatch"
            record["problems"] = problems
            print(f"  MISMATCH {rung.name}: this rung is not what it claims")
            for p in problems:
                print(f"      {p}")
            return record

        record["status"] = "ok"
        record["endpoints"] = {}
        record["quiesce"] = {}
        record["profile"] = {
            "rates": dict(args.rates_by_endpoint),
            "step_seconds": args.step_seconds, "drain_seconds": args.drain_seconds,
            "warmup_seconds": args.warmup_seconds, "warmup_rate": args.warmup_rate,
            "p99_budget_ms": args.p99_budget_ms, "workers": args.workers,
            "max_vus": args.max_vus,
        }
        invalid: list[str] = []
        health_url = f"http://127.0.0.1:{args.port}/healthz"
        for i, endpoint in enumerate(args.endpoints):
            if i:
                settled = quiesce(health_url, args.quiesce_seconds)
                record["quiesce"][endpoint] = settled
                if not settled["settled"]:
                    print(f"  WARNING {endpoint}: the service did not settle in "
                          f"{args.quiesce_seconds}s after the previous endpoint "
                          f"(slowest probe {settled['slowest_probe_s']}s); this "
                          f"verdict measures that backlog too")
                elif settled["waited_s"] > 5:
                    print(f"  {endpoint}: settled after {settled['waited_s']}s")
            verdict = run_ramp(rung, endpoint, args, attempt)
            if verdict is not None:
                ok, why = ramp_validity(verdict)
                verdict["valid"] = ok
                if not ok:
                    verdict["invalid_reason"] = why
                    invalid.append(endpoint)
                    print(f"  INVALID {endpoint}: {why}. This is not a capacity, "
                          f"it is a failed measurement.")
            record["endpoints"][endpoint] = verdict
        record["invalid_endpoints"] = invalid
        return record
    finally:
        stop_service(proc)
        record["finished_at"] = datetime.now(UTC).isoformat()


def record_span(records: list[dict]) -> dict:
    stamped = sorted(((r["started_at"], r["rung"]) for r in records
                      if r.get("started_at")), key=lambda x: x[0])
    if len(stamped) < 2:
        return {"hours": 0.0, "gap_hours": 0.0}
    first, last = datetime.fromisoformat(stamped[0][0]), datetime.fromisoformat(stamped[-1][0])
    worst = 0.0
    after = before = ""
    for (t0, r0), (t1, r1) in zip(stamped, stamped[1:]):
        gap = (datetime.fromisoformat(t1) - datetime.fromisoformat(t0)).total_seconds() / 3600
        if gap > worst:
            worst, after, before = gap, r0, r1
    return {"hours": round((last - first).total_seconds() / 3600, 1),
            "gap_hours": round(worst, 1), "gap_after": after, "gap_before": before}


def merge_records(path: Path, fresh: list[dict]) -> list[dict]:
    kept: list[dict] = []
    if path.exists():
        try:
            kept = json.loads(path.read_text()).get("records", [])
        except (json.JSONDecodeError, OSError):
            kept = []
    ran = {r.get("rung") for r in fresh}
    merged = [r for r in kept if r.get("rung") not in ran] + fresh
    merged.sort(key=lambda r: (str(r.get("rung")), r.get("attempt", 0)))
    return merged


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--only", default="", help="comma-separated rung names")
    ap.add_argument("--endpoints", default="recommend,similar,events")
    ap.add_argument("--dep-extra", default="c", choices=("c", "pure"),
                    help="the C-vs-Python axis: which dependency pole to measure")
    ap.add_argument("--rates", default="100,200,300,500,1000",
                    help="one ladder for every endpoint, or per-endpoint groups: "
                         "'recommend=50,100,150;similar=200,400,800'")
    ap.add_argument("--step-seconds", type=int, default=60)
    ap.add_argument("--drain-seconds", type=int, default=15)
    ap.add_argument("--warmup-seconds", type=int, default=90)
    ap.add_argument("--warmup-rate", type=int, default=50)
    ap.add_argument("--p99-budget-ms", type=int, default=1000)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--port", type=int, default=8100)
    ap.add_argument("--db-host", default=os.environ.get("RECSYS_DB_HOST", "127.0.0.1"))
    ap.add_argument("--service-cpus", default=os.environ.get("RECSYS_SERVICE_CPUSET", ""),
                    help="cpuset for the service under measurement, e.g. 2-5. "
                         "Empty leaves it to the scheduler")
    ap.add_argument("--load-cpus", default=os.environ.get("RECSYS_LOAD_CPUSET", ""),
                    help="cpuset for k6 and the fixture reset: not the service's")
    ap.add_argument("--no-fixture-reset", action="store_true",
                    help="do not truncate impressions between rungs. Only for a "
                         "read-only database: without the reset, later rungs measure "
                         "the backfill path rather than the ranking path")
    ap.add_argument("--n-users", type=int, default=3000)
    ap.add_argument("--n-items", type=int, default=20000)
    ap.add_argument("--boot-timeout", type=float, default=300.0)
    ap.add_argument("--repeats", type=int, default=1,
                    help="measure every rung this many times, round-robin, so a "
                         "spread can be quoted instead of a single sample")
    ap.add_argument("--max-vus", type=int, default=4000,
                    help="ceiling on requests in flight; past capacity each one "
                         "pins whatever that request allocated")
    ap.add_argument("--quiesce-seconds", type=float, default=180.0,
                    help="how long to let the service work off the previous "
                         "endpoint's backlog before timing the next one")
    ap.add_argument("--python", default=str(ROOT / ".venv" / "bin" / "python"))
    ap.add_argument("--k6", default=shutil.which("k6") or "k6")
    ap.add_argument("--out", default=str(ROOT / "load" / "results"))
    ap.add_argument("--available-images", default="",
                    help="comma-separated interpreter images that exist")
    ap.add_argument("--repeat-first", action=argparse.BooleanOptionalAction,
                    default=True,
                    help="re-run the first rung at the end to test host drift")
    args = ap.parse_args()

    args.endpoints = [e for e in args.endpoints.split(",") if e]
    args.available_images = {i for i in args.available_images.split(",") if i}
    args.rates_by_endpoint = parse_rates(args.rates, args.endpoints)

    rungs = ladder(args.dep_extra)
    if args.only:
        wanted = {n for n in args.only.split(",") if n}
        rungs = [r for r in rungs if r.name in wanted]

    if args.list or not args.run:
        print(f"{'rung':<26} {'image':<16} note")
        for r in rungs:
            print(f"{r.name:<26} {(r.image or '-'):<16} {r.note}")
        print(f"\n{len(rungs)} rungs x {len(args.endpoints)} endpoints, "
              f"dep_extra={args.dep_extra}")
        if not args.run:
            print("\nnothing run: pass --run")
        return

    Path(args.out).mkdir(parents=True, exist_ok=True)
    records = []
    print(f"ladder: {len(rungs)} rungs, endpoints={args.endpoints}, "
          f"dep_extra={args.dep_extra}, db={args.db_host}")
    if args.service_cpus:
        print(f"  cpus: service={args.service_cpus} generator={args.load_cpus or 'unpinned'} "
              f"database={os.environ.get('RECSYS_DB_CPUSET') or 'unpinned'}")
    else:
        print("  WARNING: the service is not pinned, so it shares cores with "
              "everything else on this host. Recorded, not corrected.")
    if args.db_host in ("127.0.0.1", "localhost"):
        print("  WARNING: the database is on this host. Cores can be kept apart, "
              "caches and memory bandwidth cannot. Recorded, not corrected.")

    for attempt in range(1, args.repeats + 1):
        if args.repeats > 1:
            print(f"\n===== pass {attempt} of {args.repeats} =====")
        for rung in rungs:
            print(f"\n>>> {rung.name}" + (f" (pass {attempt})" if args.repeats > 1 else ""))
            records.append(run_rung(rung, args, attempt=attempt))

    if args.repeat_first:
        print(f"\n>>> {rungs[0].name} (repeat, drift check)")
        records.append(run_rung(rungs[0], args, attempt=args.repeats + 1))

    manifest = {
        "generated_at": datetime.now(UTC).isoformat(),
        "dep_extra": args.dep_extra,
        "endpoints": args.endpoints,
        "profile_note": "describes THIS invocation only; every record carries "
                        "the profile that actually produced it, and they differ "
                        "when the ladder was run in several passes",
        "profile": {"rates": args.rates_by_endpoint,
                    "step_seconds": args.step_seconds,
                    "warmup_seconds": args.warmup_seconds,
                    "p99_budget_ms": args.p99_budget_ms, "workers": args.workers},
        "hosts": {"service": "localhost", "database": args.db_host,
                  "load_generator": "localhost",
                  "note": "a measured run puts the database and the generator on "
                          "other hosts; this field records what actually happened"},
        "cpus": {"service": args.service_cpus or None,
                 "load_generator": args.load_cpus or None,
                 "database": os.environ.get("RECSYS_DB_CPUSET") or None,
                 "note": "cpusets of the three tenants when they share this host"},
        "records": records,
    }
    path = Path(args.out) / f"ladder-{args.dep_extra}.json"
    manifest["records"] = merge_records(path, records)
    manifest["span"] = record_span(manifest["records"])
    path.write_text(json.dumps(manifest, indent=1, default=str))
    print(f"\nmanifest -> {path}")
    span = manifest["span"]
    if span.get("gap_hours", 0) >= 1:
        print(f"  WARNING: these records span {span['hours']}h with a "
              f"{span['gap_hours']}h gap between {span['gap_after']} and "
              f"{span['gap_before']}. The drift check brackets one pass, not the "
              f"gap: rungs either side of it were not measured under one host "
              f"state, and comparing across it is not evidence.")
    _summarise(records, args)


def repeatability(records: list[dict], endpoints: list[str]) -> dict:
    by: dict[tuple[str, str], list[float]] = {}
    for rec in records:
        if rec.get("status") != "ok":
            continue
        for ep in endpoints:
            v = (rec.get("endpoints") or {}).get(ep)
            if not v or v.get("valid") is False:
                continue
            passed = [s for s in v.get("steps", []) if s.get("passed") and s.get("p50")]
            if passed:
                by.setdefault((rec["rung"], ep), []).append(passed[-1]["p50"])
    out = {}
    for key, vals in by.items():
        if len(vals) < 2:
            continue
        lo, hi = min(vals), max(vals)
        out[key] = (len(vals), lo, hi, (hi - lo) / lo * 100)
    return out


def _summarise(records: list[dict], args) -> None:
    print(f"\n{'rung':<26} {'att':>3} {'status':<10} " +
          " ".join(f"{e[:9]:>10}" for e in args.endpoints))
    for rec in records:
        caps = []
        for endpoint in args.endpoints:
            verdict = (rec.get("endpoints") or {}).get(endpoint)
            if not verdict:
                caps.append(f"{'-':>10}")
            elif verdict.get("valid") is False:
                caps.append(f"{'INVALID':>10}")
            else:
                caps.append(f"{verdict['capacity_rps']:>10}")
        print(f"{rec['rung']:<26} {rec['attempt']:>3} {rec['status']:<10} "
              + " ".join(caps))

    spread = repeatability(records, args.endpoints)
    if spread:
        print("\nrepeatability: p50 at the top passing rate, across passes")
        worst = 0.0
        for (rung, ep), (n, lo, hi, pct) in sorted(spread.items()):
            worst = max(worst, pct)
            print(f"  {rung:<24} {ep:<10} n={n}  {lo:7.1f}..{hi:7.1f} ms  spread {pct:4.1f}%")
        print(f"  worst spread {worst:.1f}%: differences below it are not claimable")

    first = next((r for r in records if r["attempt"] == 1 and r["status"] == "ok"), None)
    repeat = next((r for r in records if r["attempt"] == 2), None)
    if first and repeat and repeat["status"] == "ok":
        for endpoint in args.endpoints:
            a = (first.get("endpoints") or {}).get(endpoint)
            b = (repeat.get("endpoints") or {}).get(endpoint)
            if a and b:
                agree = a["capacity_rps"] == b["capacity_rps"]
                print(f"  drift check {endpoint}: {a['capacity_rps']} vs "
                      f"{b['capacity_rps']} rps -- "
                      f"{'agree' if agree else 'DISAGREE, run not comparable'}")


if __name__ == "__main__":
    main()
