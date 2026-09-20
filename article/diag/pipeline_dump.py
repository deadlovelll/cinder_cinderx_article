import argparse
import difflib
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUT = HERE / "dumps"
SRC = OUT / "src"

FORK = ROOT / "build" / "venv-fork" / "bin" / "python"
TIER2 = ROOT / "build" / "venv-tier2" / "bin" / "python"

SPIN = """from __future__ import annotations


SCALE = 16


def spin(x: int, n: int) -> int:
    total = 0
    i = 0
    while i < n:
        total = total + x * i
        i = i + 1
    return total * SCALE
"""

BORROW = """from __future__ import annotations


def borrow(n: int) -> object:
    out = None
    i = 0
    while i < n:
        out = "abc"
        i = i + 1
    return out
"""

ARGS = (3, 64)
EXPECTED = 96768
WARMUP = 1000
JIT_AUTO = 300

HEADER = re.compile(r"^JIT: \S+ -- (.+?):?$")


def slug(title: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "-", title).strip("-").lower()
    return s[:80]


def split_sections(raw: Path, dest: Path) -> list[tuple[str, int]]:
    dest.mkdir(parents=True, exist_ok=True)
    for old in dest.glob("*.txt"):
        old.unlink()
    sections: list[tuple[str, list[str]]] = []
    current: list[str] | None = None
    for line in raw.read_text(errors="replace").splitlines():
        m = HEADER.match(line)
        if m is not None:
            current = []
            sections.append((m.group(1), current))
            continue
        if current is not None:
            current.append(line)
    out: list[tuple[str, int]] = []
    for n, (title, body) in enumerate(sections, 1):
        while body and not body[-1].strip():
            body.pop()
        path = dest / f"{n:02d}-{slug(title)}.txt"
        path.write_text("\n".join(body) + "\n")
        out.append((str(path.relative_to(OUT)), len(body)))
    return out


def run(label: str, argv: list[str], out: Path, err: Path,
        env: dict[str, str] | None = None) -> int:
    full = dict(os.environ)
    full.update(env or {})
    full["PYTHONPATH"] = str(SRC)
    proc = subprocess.run(argv, cwd=str(SRC), env=full, capture_output=True, text=True)
    out.write_text(proc.stdout)
    err.write_text(proc.stderr)
    status = "ok" if proc.returncode == 0 else f"rc={proc.returncode}"
    print(f"  {label:<28} {status:<8} stdout={len(proc.stdout.splitlines())}l "
          f"stderr={len(proc.stderr.splitlines())}l")
    return proc.returncode


def worker_cinderx_bytecode() -> None:
    import dis

    import cinderx

    cinderx.install_frame_evaluator()
    from spin import spin

    print("### cold bytecode (dis.dis, adaptive=False)")
    dis.dis(spin)
    for _ in range(WARMUP):
        assert spin(*ARGS) == EXPECTED
    print()
    print("### specialized bytecode after %d calls (dis.dis, adaptive=True)" % WARMUP)
    dis.dis(spin, adaptive=True)


def worker_cinderx_compile() -> None:
    import cinderx
    import cinderx.jit

    cinderx.install_frame_evaluator()
    from spin import spin

    for _ in range(WARMUP):
        assert spin(*ARGS) == EXPECTED
    print("jit_compiled=%s code_size=%d bytes" % (
        cinderx.jit.is_jit_compiled(spin), cinderx.jit.get_compiled_size(spin)))


def worker_cinderx_disassemble() -> None:
    import cinderx
    import cinderx.jit

    cinderx.install_frame_evaluator()
    from spin import spin

    for _ in range(WARMUP):
        assert spin(*ARGS) == EXPECTED
    assert cinderx.jit.is_jit_compiled(spin)
    cinderx.jit.disassemble(spin)


def worker_tier2_bytecode() -> None:
    import dis
    import sys

    from spin import spin

    print("sys._jit.is_enabled() =", sys._jit.is_enabled())
    print("### cold bytecode (dis.dis, adaptive=False)")
    dis.dis(spin)
    for _ in range(WARMUP):
        assert spin(*ARGS) == EXPECTED
    print()
    print("### specialized bytecode after %d calls (dis.dis, adaptive=True)" % WARMUP)
    dis.dis(spin, adaptive=True)


def executors(code: object) -> list[tuple[int, object]]:
    import _opcode

    found = []
    for off in range(0, len(code.co_code), 2):
        try:
            ex = _opcode.get_executor(code, off)
        except (ValueError, RuntimeError):
            continue
        if ex is not None:
            found.append((off, ex))
    return found


def print_trace(off: int, ex: object) -> None:
    print("# executor at bytecode offset %d, %d uops" % (off, len(ex)))
    for n, (name, oparg, target, operand) in enumerate(ex):
        print("%3d  %-34s oparg=%-6d target=%-4d operand=%#x" % (n, name, oparg, target, operand))


def worker_tier2_uops() -> None:
    import os

    from spin import spin

    for _ in range(WARMUP):
        assert spin(*ARGS) == EXPECTED
    mode = os.environ.get("PYTHON_UOPS_OPTIMIZE", "(unset)")
    print("# PYTHON_UOPS_OPTIMIZE=%s" % mode)
    found = executors(spin.__code__)
    if not found:
        print("# no executors")
        return
    for off, ex in found:
        print_trace(off, ex)


def worker_tier2_machine() -> None:
    from spin import spin

    for _ in range(WARMUP):
        assert spin(*ARGS) == EXPECTED
    found = executors(spin.__code__)
    if not found:
        print("# no executors")
        return
    off, ex = found[0]
    blob = ex.get_jit_code()
    if blob is None:
        print("# executor has no machine code")
        return
    used = len(blob.rstrip(b"\x00"))
    (OUT / "tier2" / "06-machine-code.bin").write_bytes(blob)
    print("# executor at offset %d: %d bytes allocated, %d bytes before zero padding"
          % (off, len(blob), used))


def worker_tier2_borrow() -> None:
    import os

    from borrow import borrow

    for _ in range(WARMUP):
        borrow(64)
    print("# PYTHON_UOPS_OPTIMIZE=%s" % os.environ.get("PYTHON_UOPS_OPTIMIZE", "(unset)"))
    for off, ex in executors(borrow.__code__):
        print_trace(off, ex)


WORKERS = {
    "cinderx-bytecode": worker_cinderx_bytecode,
    "cinderx-compile": worker_cinderx_compile,
    "cinderx-disassemble": worker_cinderx_disassemble,
    "tier2-bytecode": worker_tier2_bytecode,
    "tier2-uops": worker_tier2_uops,
    "tier2-machine": worker_tier2_machine,
    "tier2-borrow": worker_tier2_borrow,
}


def jit_flags(*extra: str) -> list[str]:
    base = [
        "-X", "cinderx-jit-auto=%d" % JIT_AUTO,
        "-X", "cinderx-jit-list-file=%s" % (SRC / "jitlist.txt"),
        "-X", "cinderx-jit-asm-syntax=att",
    ]
    return base + [a for f in extra for a in ("-X", f)]


def me(worker: str) -> list[str]:
    return [str(HERE / "pipeline_dump.py"), "--worker", worker]


def collect_cinderx() -> None:
    d = OUT / "cinderx"
    d.mkdir(parents=True, exist_ok=True)
    print("CinderX (build/venv-fork)")

    run("00 jit flags", [str(FORK), "-X", "cinderx-jit-help", "-c", "import cinderx"],
        d / "00-jit-flags.txt", d / "00-jit-flags.err")

    run("01 bytecode", [str(FORK)] + me("cinderx-bytecode"),
        d / "01-bytecode.txt", d / "01-bytecode.err")

    run("03 hir initial", [str(FORK)] + jit_flags("cinderx-jit-dump-hir") + me("cinderx-compile"),
        d / "03-hir-initial.stdout.txt", d / "03-hir-initial.raw.txt")
    split_sections(d / "03-hir-initial.raw.txt", d / "03-hir-initial")

    run("04 hir passes", [str(FORK)] + jit_flags(
        "cinderx-jit-dump-hir-passes", "cinderx-jit-dump-final-hir") + me("cinderx-compile"),
        d / "04-hir-passes.stdout.txt", d / "04-hir-passes.raw.txt")
    split_sections(d / "04-hir-passes.raw.txt", d / "04-hir-passes")

    run("05 hir stats", [str(FORK)] + jit_flags("cinderx-jit-dump-hir-stats")
        + me("cinderx-compile"),
        d / "05-hir-stats.stdout.txt", d / "05-hir-stats.txt")

    run("05b refcount debug", [str(FORK)] + jit_flags("cinderx-jit-debug-refcount")
        + me("cinderx-compile"),
        d / "05b-refcount-debug.stdout.txt", d / "05b-refcount-debug.txt")

    run("06 lir", [str(FORK)] + jit_flags("cinderx-jit-dump-lir") + me("cinderx-compile"),
        d / "06-lir.stdout.txt", d / "06-lir.raw.txt")
    split_sections(d / "06-lir.raw.txt", d / "06-lir")

    run("06b lir with origin", [str(FORK)] + jit_flags("cinderx-jit-dump-lir-origin")
        + me("cinderx-compile"),
        d / "06b-lir-origin.stdout.txt", d / "06b-lir-origin.raw.txt")
    split_sections(d / "06b-lir-origin.raw.txt", d / "06b-lir-origin")

    run("06c regalloc debug", [str(FORK)] + jit_flags("cinderx-jit-debug-regalloc")
        + me("cinderx-compile"),
        d / "06c-regalloc-debug.stdout.txt", d / "06c-regalloc-debug.txt")

    run("07 asm", [str(FORK)] + jit_flags("cinderx-jit-dump-asm") + me("cinderx-compile"),
        d / "07-asm.stdout.txt", d / "07-asm.raw.txt")
    split_sections(d / "07-asm.raw.txt", d / "07-asm")

    run("07b jit.disassemble", [str(FORK)] + jit_flags() + me("cinderx-disassemble"),
        d / "07b-disassemble.txt", d / "07b-disassemble.err")


def collect_tier2() -> None:
    d = OUT / "tier2"
    d.mkdir(parents=True, exist_ok=True)
    print("CPython tier 2 (build/venv-tier2)")

    run("01 bytecode", [str(TIER2)] + me("tier2-bytecode"),
        d / "01-bytecode.txt", d / "01-bytecode.err")

    run("03 uops before opt", [str(TIER2)] + me("tier2-uops"),
        d / "03-uops-before-analysis.txt", d / "03-uops-before-analysis.err",
        env={"PYTHON_UOPS_OPTIMIZE": "0"})

    run("04 uops after opt", [str(TIER2)] + me("tier2-uops"),
        d / "04-uops-after-analysis.txt", d / "04-uops-after-analysis.err")

    run("06 machine code", [str(TIER2)] + me("tier2-machine"),
        d / "06-machine-code.txt", d / "06-machine-code.err")
    blob = d / "06-machine-code.bin"
    objdump = shutil.which("objdump")
    if blob.exists() and objdump:
        used = len(blob.read_bytes().rstrip(b"\x00"))
        trimmed = d / "06-machine-code.trimmed.bin"
        trimmed.write_bytes(blob.read_bytes()[:used])
        asm = subprocess.run(
            [objdump, "-D", "-b", "binary", "-m", "i386:x86-64", "-M", "intel", str(trimmed)],
            capture_output=True, text=True)
        (d / "06-machine-code.objdump.txt").write_text(asm.stdout)
        print("  %-28s %-8s %dl" % ("06b objdump", "ok", len(asm.stdout.splitlines())))

    uop_diff(d / "03-uops-before-analysis.txt", d / "04-uops-after-analysis.txt",
             d / "05-uops-analysis.diff")

    run("07 borrow before opt", [str(TIER2)] + me("tier2-borrow"),
        d / "07-borrow-before-analysis.txt", d / "07-borrow-before-analysis.err",
        env={"PYTHON_UOPS_OPTIMIZE": "0"})
    run("07 borrow after opt", [str(TIER2)] + me("tier2-borrow"),
        d / "07-borrow-after-analysis.txt", d / "07-borrow-after-analysis.err")
    uop_diff(d / "07-borrow-before-analysis.txt", d / "07-borrow-after-analysis.txt",
             d / "07-borrow-analysis.diff")


def opnames(path: Path) -> list[str]:
    out = []
    for line in path.read_text().splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0].isdigit() and parts[1].startswith("_"):
            out.append(parts[1])
    return out


def uop_diff(before: Path, after: Path, dest: Path) -> None:
    a, b = opnames(before), opnames(after)
    diff = difflib.unified_diff(a, b, "before-analysis", "after-analysis", lineterm="", n=2)
    dest.write_text("\n".join(diff) + "\n")
    print("  %-28s %-8s %d -> %d uops" % (dest.name, "ok", len(a), len(b)))


def write_manifest() -> None:
    lines = []
    for path in sorted(OUT.rglob("*")):
        if path.is_dir() or "__pycache__" in path.parts:
            continue
        rel = path.relative_to(OUT)
        if path.suffix == ".bin":
            lines.append("%-64s %d bytes" % (rel, path.stat().st_size))
        else:
            n = len(path.read_text(errors="replace").splitlines())
            lines.append("%-64s %d lines" % (rel, n))
    (OUT / "MANIFEST.txt").write_text("\n".join(lines) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--worker")
    ap.add_argument("--only", choices=("cinderx", "tier2"))
    args = ap.parse_args()

    if args.worker:
        WORKERS[args.worker]()
        return

    SRC.mkdir(parents=True, exist_ok=True)
    (SRC / "spin.py").write_text(SPIN)
    (SRC / "borrow.py").write_text(BORROW)
    (SRC / "jitlist.txt").write_text("spin:spin\n")

    if args.only in (None, "cinderx"):
        collect_cinderx()
    if args.only in (None, "tier2"):
        collect_tier2()
    shutil.rmtree(SRC / "__pycache__", ignore_errors=True)
    write_manifest()
    print("dumps in %s" % OUT)


if __name__ == "__main__":
    main()
