"""The candidate generator across the full matrix, measured directly."""

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
    """mode: off | runtime | jit. Must run before the kernels are imported."""
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
    from recsys.infrastructure.db.engine import create_engine
    from recsys.infrastructure.db.user_repository import SqlUserRepository
    from recsys.infrastructure.graph import CovisitationGraph, count_items
    from recsys.settings import Settings

    engine = create_engine(Settings.from_env())
    n_items = await count_items(engine)
    graph = CovisitationGraph(engine, n_items)
    await graph.load()
    users = SqlUserRepository(engine)
    contexts = []
    uid = 1
    while len(contexts) < n_users and uid < n_users * 5:
        ctx = await users.load_context(uid)
        if ctx is not None and ctx.recent_items:
            contexts.append(ctx)
        uid += 1
    await engine.dispose()
    return graph.csr(), n_items, contexts


def make_cells(csr, n_items: int, jit_on: bool):
    """One callable per cell, plus what to force_compile for it."""
    from recsys.domain.kernels import walk_plain as wp
    from recsys.domain.kernels import walk_static as ws

    plain_scores = [0] * n_items
    plain_touched = [0] * n_items
    static_scores = ws.from_list(plain_scores, n_items)
    static_touched = ws.from_list(plain_touched, n_items)
    out_ids = ws.from_list([0] * CANDIDATE_LIMIT, CANDIDATE_LIMIT)
    out_scores = ws.from_list([0] * CANDIDATE_LIMIT, CANDIDATE_LIMIT)
    seed_cache: dict[int, object] = {}

    def plain(select, ctx):
        n = wp.walk(csr.indptr, csr.indices, csr.weights, ctx.recent_items,
                    plain_scores, plain_touched)
        result = select(plain_scores, plain_touched, n, CANDIDATE_LIMIT, frozenset())
        wp.reset(plain_scores, plain_touched, n)
        return result

    def static_seeds(ctx):
        key = id(ctx)
        arr = seed_cache.get(key)
        if arr is None:
            arr = ws.from_list(list(ctx.recent_items), len(ctx.recent_items))
            seed_cache[key] = arr
        return arr

    def static_bounded(ctx):
        seeds = static_seeds(ctx)
        n = ws.walk(csr.indptr, csr.indices, csr.weights, seeds,
                    len(ctx.recent_items), static_scores, static_touched)
        k = ws.take_top_ids(static_scores, static_touched, n, CANDIDATE_LIMIT,
                            out_ids, out_scores)
        result = ws.boxed_pairs(out_ids, out_scores, k)
        ws.reset(static_scores, static_touched, n)
        return result

    def static_sorted(ctx):
        seeds = static_seeds(ctx)
        n = ws.walk(csr.indptr, csr.indices, csr.weights, seeds,
                    len(ctx.recent_items), static_scores, static_touched)
        result = ws.select_sorted(static_scores, static_touched, n, CANDIDATE_LIMIT)
        ws.reset(static_scores, static_touched, n)
        return result

    return {
        "plain/bounded": (lambda ctx: plain(wp.select_bounded, ctx),
                          [wp.walk, wp.select_bounded, wp.reset]),
        "plain/sorted": (lambda ctx: plain(wp.select_sorted, ctx),
                         [wp.walk, wp.select_sorted, wp.reset]),
        "static/bounded": (static_bounded,
                           [ws.walk, ws.take_top_ids, ws.reset, ws.boxed_pairs]),
        "static/sorted": (static_sorted,
                          [ws.walk, ws.select_sorted, ws.reset]),
    }


def reference(cells, contexts) -> dict[int, list]:
    """plain/sorted is the reference every other cell must reproduce."""
    fn, _ = cells["plain/sorted"]
    return {i: sorted(fn(ctx)) for i, ctx in enumerate(contexts)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=("off", "runtime", "jit"), required=True)
    ap.add_argument("--users", type=int, default=40)
    ap.add_argument("--reps", type=int, default=7)
    ap.add_argument("--out", default=str(ROOT / "load" / "results"))
    args = ap.parse_args()

    facts = install_runtime(args.mode)
    csr, n_items, contexts = asyncio.run(load_inputs(args.users))
    if not contexts:
        raise SystemExit("no users with recent items: seed the fixture first")

    cells = make_cells(csr, n_items, facts["jit"])
    expected = reference(cells, contexts)

    import cinderx.jit as jit  # noqa: PLC0415
    have_jit = facts["jit"]

    records = []
    for name, (fn, hot) in cells.items():
        # one warm pass: also the correctness gate, per context
        mismatches = 0
        for i, ctx in enumerate(contexts):
            if sorted(fn(ctx)) != expected[i]:
                mismatches += 1
        compiled = 0
        if have_jit:
            for target in hot:
                if jit.force_compile(target):
                    compiled += 1
            for ctx in contexts:      # run once more so the compiled path is warm
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
