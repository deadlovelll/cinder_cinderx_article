import argparse
import json
import os
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from bench.harness import cx_pyperf as h

h.boot("cinderx_jit")

from bench.b_jit_warmup.constants import N_ITEMS, ROUNDS
from bench.b_jit_warmup.hot_index import hot_index

jit = h.jit()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--warmup", type=int, required=True)
    ap.add_argument("--reps", type=int, default=15)
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent / "out"))
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    w = args.warmup

    n = N_ITEMS
    buf = [i * 3 % 101 for i in range(n)]
    s = sum(buf[i] * buf[n - 1 - i] for i in range(n))
    expected = ROUNDS * s + n * ROUNDS * (ROUNDS - 1) // 2

    def work() -> int:
        return hot_index(buf, ROUNDS)

    jit.get_and_clear_runtime_stats()
    try:
        jit.get_and_clear_inline_cache_stats()
    except Exception:
        pass

    for _ in range(w):
        work()

    before = jit.count_interpreted_calls(hot_index)
    ok = jit.force_compile(hot_index)
    assert work() == expected, "checksum mismatch"

    facts = {
        "warmup": w,
        "interpreted_calls_before_compile": before,
        "force_compile": bool(ok),
        "is_jit_compiled": bool(jit.is_jit_compiled(hot_index)),
        "code_bytes": jit.get_compiled_size(hot_index),
        "stack_bytes": jit.get_compiled_stack_size(hot_index),
        "spill_bytes": jit.get_compiled_spill_stack_size(hot_index),
        "compile_time_us": jit.get_function_compilation_time(hot_index),
        "inlined_functions": jit.get_num_inlined_functions(hot_index),
        "hir_opcodes": jit.get_function_hir_opcode_counts(hot_index),
    }

    times = []
    for _ in range(args.reps):
        t0 = time.perf_counter()
        work()
        times.append((time.perf_counter() - t0) * 1e3)
    facts["ms_median"] = round(statistics.median(times), 3)
    facts["ms_min"] = round(min(times), 3)
    facts["ms_all"] = [round(t, 2) for t in times]

    facts["runtime_stats"] = jit.get_and_clear_runtime_stats()
    try:
        facts["inline_cache_stats"] = jit.get_and_clear_inline_cache_stats()
    except Exception as exc:
        facts["inline_cache_stats"] = f"unavailable: {type(exc).__name__}: {exc}"

    dis_path = out / f"disasm-w{w}.txt"
    sys.stdout.flush()
    saved = os.dup(1)
    fd = os.open(dis_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
    try:
        os.dup2(fd, 1)
        try:
            jit.disassemble(hot_index)
        except Exception as exc:
            os.write(1, f"unavailable: {type(exc).__name__}: {exc}\n".encode())
        sys.stdout.flush()
    finally:
        os.dup2(saved, 1)
        os.close(saved)
        os.close(fd)
    facts["disasm_lines"] = len(dis_path.read_text(errors="replace").splitlines())

    (out / f"facts-w{w}.json").write_text(json.dumps(facts, indent=1, default=str))
    print(json.dumps({k: v for k, v in facts.items()
                      if k not in ("ms_all", "hir_opcodes", "inline_cache_stats")},
                     indent=1, default=str))


if __name__ == "__main__":
    main()
