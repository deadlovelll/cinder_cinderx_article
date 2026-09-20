import importlib
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable


def _setup() -> None:
    import cinderx
    import cinderx.jit
    from cinderx.compiler.strict.loader import install

    cinderx.jit.disable()
    cinderx.install_frame_evaluator()
    install()
    sys.path.insert(0, ROOT)


def _modules(subdir: str) -> list[str]:
    d = os.path.join(ROOT, subdir)
    if not os.path.isdir(d):
        return []
    return sorted(
        f[:-3] for f in os.listdir(d)
        if f.endswith(".py") and not f.startswith("_")
    )


def run_ok() -> list[dict]:
    from _static import is_static_module

    out = []
    for name in _modules("ok"):
        rec: dict = {"module": name}
        try:
            mod = importlib.import_module(f"ok.{name}")
            rec["static"] = bool(is_static_module(mod))
            rec["doc"] = (mod.__doc__ or "").strip()
            rec["rows"] = list(mod.demo())
            rec["status"] = "ok"
        except BaseException as exc:
            rec["status"] = "broken"
            rec["error"] = f"{type(exc).__name__}: {exc}"
        out.append(rec)
    return out


def run_errors() -> list[dict]:
    out = []
    d = os.path.join(ROOT, "errors")
    for name in _modules("errors"):
        path = os.path.join(d, f"{name}.py")
        proc = subprocess.run(
            [PY, "-m", "cinderx.compiler", "--static", path, "--modname", name],
            capture_output=True, text=True, timeout=120,
        )
        head = open(path).readline().strip().lstrip("# ").strip('"')
        diag = ""
        for line in reversed(proc.stderr.splitlines()):
            if "Error:" in line or "error" in line.lower():
                diag = line.strip()
                break
        out.append({
            "snippet": name,
            "what": head,
            "rejected": proc.returncode != 0,
            "diagnostic": diag or "(compiled without error)",
        })
    return out


def as_text(ok: list[dict], errs: list[dict]) -> None:
    for rec in ok:
        print(f"\n=== ok/{rec['module']}   static={rec.get('static')}   {rec['status']}")
        if rec["status"] != "ok":
            print(f"    !! {rec['error']}")
            continue
        for label, value in rec["rows"]:
            print(f"    {label:<44} {value}")
    print("\n=== errors/ (must be rejected at compile time)")
    for rec in errs:
        mark = "rejected" if rec["rejected"] else "NOT REJECTED"
        print(f"    {rec['snippet']:<34} {mark}")
        print(f"        {rec['diagnostic']}")


def main() -> None:
    _setup()
    ok, errs = run_ok(), run_errors()
    as_text(ok, errs)
    broken = [r for r in ok if r["status"] != "ok"]
    missed = [r for r in errs if not r["rejected"]]
    if broken or missed:
        print(f"\n{len(broken)} broken example(s), {len(missed)} snippet(s) "
              f"that should have been rejected", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
