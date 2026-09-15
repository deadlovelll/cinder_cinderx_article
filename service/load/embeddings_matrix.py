
from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

CANDIDATE_LIMIT = 200


def install_runtime(mode: str) -> dict:
    facts = {"mode": mode, "frame_evaluator": False, "jit": False,
             "static_loader": False}
    if mode == "off":
        return facts
    import cinderx
    import cinderx.jit

    cinderx.install_frame_evaluator()
    from cinderx.compiler.strict.loader import install

    install()
    facts["frame_evaluator"] = cinderx.is_frame_evaluator_installed()
    facts["static_loader"] = True
    if mode == "jit":
        cinderx.jit.enable()
    else:
        cinderx.jit.disable()
    facts["jit"] = cinderx.jit.is_enabled()
    return facts


def store_class(impl: str):
    if impl == "numpy":
        from recsys.infrastructure.embeddings_numpy import NumpyEmbeddingStore

        return NumpyEmbeddingStore
    if impl == "static":
        from recsys.infrastructure.embeddings_static import StaticEmbeddingStore

        return StaticEmbeddingStore
    from recsys.infrastructure.embeddings_python import PythonEmbeddingStore

    return PythonEmbeddingStore


def hot_functions(impl: str, cls) -> list:
    if impl == "static":
        from recsys.domain.kernels import similar_static as k

        return [k.score_all, k.take_top, k.boxed_pairs]
    return [cls.similar]


async def load_store(impl: str):
    from recsys.infrastructure.db.engine import create_engine
    from recsys.settings import Settings

    engine = create_engine(Settings.from_env())
    store = store_class(impl)(engine)
    await store.load()
    await engine.dispose()
    return store


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=("off", "runtime", "jit"), required=True)
    ap.add_argument("--impls", default="numpy,python,static")
    ap.add_argument("--items", type=int, default=3)
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--out", default=str(ROOT / "load" / "results"))
    args = ap.parse_args()

    os.environ["RECSYS_KERNEL"] = "plain"

    impls = [i for i in args.impls.split(",") if i]
    if args.mode == "off" and "static" in impls:
        impls = [i for i in impls if i != "static"]
        print("   static skipped in mode off: the loader is not installed")

    facts = install_runtime(args.mode)
    have_jit = facts["jit"]
    jit = None
    if have_jit:
        import cinderx.jit as jit

    reference: tuple | None = None
    ties = 0
    records = []
    for impl in impls:
        cls = store_class(impl)
        store = asyncio.run(load_store(impl))
        ids = [store._ids[i] for i in range(0, len(store._ids),
                                            max(1, len(store._ids) // args.items))]
        ids = ids[:args.items]
        if not ids:
            raise SystemExit("no embeddings: seed the fixture first")

        compiled = 0
        if have_jit:
            for fn in hot_functions(impl, cls):
                try:
                    if jit.force_compile(fn):
                        compiled += 1
                except Exception as exc:
                    print(f"   force_compile({impl}): {exc}")

        got = [store.similar(i, CANDIDATE_LIMIT) for i in ids]
        scores = [[s for _, s in page] for page in got]
        id_sets = [{iid for iid, _ in page} for page in got]
        if reference is None:
            reference = (scores, id_sets)
            mismatches = ties = 0
        else:
            ref_scores, ref_ids = reference
            mismatches = sum(1 for a, b in zip(scores, ref_scores) if a != b)
            ties = sum(1 for a, b, sa, sb in zip(id_sets, ref_ids, scores, ref_scores)
                       if a != b and sa == sb)

        per_call = []
        for _ in range(args.reps):
            t0 = time.perf_counter()
            for i in ids:
                store.similar(i, CANDIDATE_LIMIT)
            per_call.append((time.perf_counter() - t0) * 1e3 / len(ids))
        per_call.sort()

        records.append({
            "impl": impl, "mode": args.mode, "jit": have_jit,
            "median_ms": statistics.median(per_call),
            "min_ms": per_call[0], "max_ms": per_call[-1],
            "reps": args.reps, "items": len(ids),
            "compiled_functions": compiled, "mismatches": mismatches,
            "tie_breaks": ties,
        })
        flag = "" if mismatches == 0 else f"  MISMATCH x{mismatches}"
        if ties:
            flag += f"  (ties at the cut: {ties})"
        print(f"  {impl:8s} {statistics.median(per_call):9.2f} ms/request  "
              f"compiled={compiled}{flag}")

    Path(args.out).mkdir(parents=True, exist_ok=True)
    path = Path(args.out) / f"embeddings_matrix-{args.mode}.json"
    path.write_text(json.dumps({"facts": facts,
                                "candidate_limit": CANDIDATE_LIMIT,
                                "reference": "the first implementation listed",
                                "cells": records}, indent=1))
    print(f"  -> {path}")


if __name__ == "__main__":
    main()
