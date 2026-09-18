
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

CANDIDATE_LIMIT = 400


def install_runtime(mode: str) -> dict:
    facts = {"mode": mode, "frame_evaluator": False, "jit": False, "static_loader": False}
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


async def load_inputs(n_users: int):
    from recsys.infrastructure.db.create_engine import create_engine
    from recsys.infrastructure.db.user_repository import SqlUserRepository
    from recsys.infrastructure.graph.count_items import count_items
    from recsys.infrastructure.graph.covisitation_graph import CovisitationGraph
    from recsys.infrastructure.catalogue.memory_catalogue import MemoryCatalogue
    from recsys.settings import Settings

    engine = create_engine(Settings.from_env())
    n_items = await count_items(engine)
    graph = CovisitationGraph(engine, n_items)
    await graph.load()
    catalogue = MemoryCatalogue(engine)
    await catalogue.load()
    users = SqlUserRepository(engine, catalogue)
    contexts = []
    uid = 1
    while len(contexts) < n_users and uid < n_users * 5:
        ctx = await users.load_context(uid)
        if ctx is not None and ctx.recent_items:
            contexts.append(ctx)
        uid += 1
    await engine.dispose()
    return graph.csr(), n_items, contexts


def make_cells(csr, n_items: int, with_static: bool = True):
    from recsys.domain.kernels import walk_plain as wp

    plain_scores = [0] * n_items
    plain_touched = [0] * n_items

    def plain(select, ctx):
        n = wp.walk(csr.indptr, csr.indices, csr.weights, ctx.recent_items,
                    plain_scores, plain_touched)
        result = select(plain_scores, plain_touched, n, CANDIDATE_LIMIT, frozenset())
        wp.reset(plain_scores, plain_touched, n)
        return result

    cells = {
        "plain/bounded": (lambda ctx: plain(wp.select_bounded, ctx),
                          [wp.walk, wp.select_bounded, wp.reset]),
        "plain/sorted": (lambda ctx: plain(wp.select_sorted, ctx),
                         [wp.walk, wp.select_sorted, wp.reset]),
    }
    if not with_static:
        return cells

    from recsys.domain.kernels import walk_static as ws

    static_indptr = ws.from_list(csr.indptr, len(csr.indptr))
    static_indices = ws.from_list(csr.indices, len(csr.indices))
    static_weights = ws.from_list(csr.weights, len(csr.weights))

    static_scores = ws.from_list(plain_scores, n_items)
    static_touched = ws.from_list(plain_touched, n_items)
    out_ids = ws.from_list([0] * CANDIDATE_LIMIT, CANDIDATE_LIMIT)
    out_scores = ws.from_list([0] * CANDIDATE_LIMIT, CANDIDATE_LIMIT)
    seed_cache: dict[int, object] = {}

    def static_seeds(ctx):
        key = id(ctx)
        arr = seed_cache.get(key)
        if arr is None:
            arr = ws.from_list(list(ctx.recent_items), len(ctx.recent_items))
            seed_cache[key] = arr
        return arr

    def static_bounded(ctx):
        seeds = static_seeds(ctx)
        n = ws.walk(static_indptr, static_indices, static_weights, seeds,
                    len(ctx.recent_items), static_scores, static_touched)
        k = ws.take_top_ids(static_scores, static_touched, n, CANDIDATE_LIMIT,
                            out_ids, out_scores)
        result = ws.boxed_pairs(out_ids, out_scores, k)
        ws.reset(static_scores, static_touched, n)
        return result

    def static_sorted(ctx):
        seeds = static_seeds(ctx)
        n = ws.walk(static_indptr, static_indices, static_weights, seeds,
                    len(ctx.recent_items), static_scores, static_touched)
        result = ws.select_sorted(static_scores, static_touched, n, CANDIDATE_LIMIT)
        ws.reset(static_scores, static_touched, n)
        return result

    cells["static/bounded"] = (static_bounded,
                               [ws.walk, ws.take_top_ids, ws.reset, ws.boxed_pairs])
    cells["static/sorted"] = (static_sorted,
                              [ws.walk, ws.select_sorted, ws.reset])
    return cells


def reference(cells, contexts) -> dict[int, list]:
    fn, _ = cells["plain/sorted"]
    return {i: sorted(fn(ctx)) for i, ctx in enumerate(contexts)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=("off", "runtime", "jit"), required=True)
    ap.add_argument("--users", type=int, default=40)
    ap.add_argument("--reps", type=int, default=7)
    ap.add_argument("--out", default=str(ROOT / "load" / "results"))
    args = ap.parse_args()

    os.environ["RECSYS_KERNEL"] = "plain"

    facts = install_runtime(args.mode)
    csr, n_items, contexts = asyncio.run(load_inputs(args.users))
    if not contexts:
        raise SystemExit("no users with recent items: seed the fixture first")

    if args.mode == "off":
        print("   static cells skipped in mode off: the loader is not installed")
    cells = make_cells(csr, n_items, with_static=args.mode != "off")
    expected = reference(cells, contexts)

    have_jit = facts["jit"]
    jit = None
    if have_jit:
        import cinderx.jit as jit

    records = []
    for name, (fn, hot) in cells.items():
        mismatches = 0
        for i, ctx in enumerate(contexts):
            if sorted(fn(ctx)) != expected[i]:
                mismatches += 1
        compiled = 0
        if have_jit:
            for target in hot:
                if jit.force_compile(target):
                    compiled += 1
            for ctx in contexts:
                fn(ctx)

        per_request = []
        for _ in range(args.reps):
            t0 = time.perf_counter()
            for ctx in contexts:
                fn(ctx)
            per_request.append((time.perf_counter() - t0) * 1e3 / len(contexts))
        per_request.sort()

        deopts = len(jit.get_and_clear_runtime_stats().get("deopt", [])) if have_jit else 0
        records.append({
            "cell": name, "mode": args.mode, "jit": have_jit,
            "median_ms": statistics.median(per_request),
            "min_ms": per_request[0], "max_ms": per_request[-1],
            "reps": args.reps, "users": len(contexts),
            "compiled_functions": compiled, "deopts": deopts,
            "mismatches": mismatches,
        })
        flag = "" if mismatches == 0 else f"  MISMATCH x{mismatches}"
        print(f"  {name:16s} {statistics.median(per_request):8.2f} ms/request  "
              f"compiled={compiled}  deopts={deopts}{flag}")

    Path(args.out).mkdir(parents=True, exist_ok=True)
    path = Path(args.out) / f"kernel_matrix-{args.mode}.json"
    path.write_text(json.dumps({"facts": facts, "n_items": n_items,
                                "candidate_limit": CANDIDATE_LIMIT,
                                "cells": records}, indent=1))
    print(f"  -> {path}")


if __name__ == "__main__":
    main()
