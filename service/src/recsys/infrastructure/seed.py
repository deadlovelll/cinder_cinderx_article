
from __future__ import annotations

import argparse
import asyncio
import base64
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, distinct, func, insert, select, text
from sqlalchemy.ext.asyncio import AsyncEngine

from recsys.infrastructure.db.engine import create_engine
from recsys.infrastructure.db.metadata import metadata
from recsys.infrastructure.db.tables.covisitation import covisitation
from recsys.infrastructure.db.tables.impressions import impressions
from recsys.infrastructure.db.tables.interactions import interactions
from recsys.infrastructure.db.tables.item_embeddings import item_embeddings
from recsys.infrastructure.db.tables.items import items
from recsys.infrastructure.db.tables.pins import pins
from recsys.infrastructure.db.tables.popularity import popularity
from recsys.infrastructure.db.tables.user_state import user_state
from recsys.infrastructure.db.tables.users import users
from recsys.settings import Settings

MASK = (1 << 64) - 1
BASE_DATE = datetime(2026, 1, 1, tzinfo=UTC)
SEGMENTS = ("new", "casual", "loyal", "bargain")
REGION_MASKS = (1, 2, 4, 3, 7)
N_CATEGORIES = 120
N_BRANDS = 300
EMBED_DIM = 64
BATCH = 5_000


def lcg(seed: int):
    x = seed & MASK
    while True:
        x = (x * 6364136223846793005 + 1442695040888963407) & MASK
        yield x >> 33


async def _insert_batched(engine: AsyncEngine, table, rows: list[dict]) -> None:
    stmt = insert(table)
    for start in range(0, len(rows), BATCH):
        async with engine.begin() as conn:
            await conn.execute(stmt, rows[start:start + BATCH])


def build_items(n_items: int, rnd) -> list[dict]:
    out = []
    for i in range(n_items):
        showable = next(rnd) % 100
        inactive = showable < 5
        out_of_stock = 5 <= showable < 10
        promoted = next(rnd) % 50 == 0
        out.append({
            "id": i,
            "category_id": next(rnd) % N_CATEGORIES,
            "brand_id": next(rnd) % N_BRANDS,
            "price_cents": 500 + next(rnd) % 200_000,
            "margin_bps": 200 + next(rnd) % 4_000,
            "active": not inactive,
            "stock": 0 if out_of_stock else 1 + next(rnd) % 50,
            "age_restricted": next(rnd) % 1000 < 30,
            "region_mask": REGION_MASKS[next(rnd) % len(REGION_MASKS)],
            "created_at": BASE_DATE - timedelta(days=next(rnd) % 400),
            "promo_multiplier_bps": (10_000 + next(rnd) % 8_000) if promoted else 10_000,
        })
    return out


def build_graph(n_items: int, avg_degree: int, rnd) -> list[dict]:
    head = max(1, n_items // 100)
    rows = []
    for src in range(n_items):
        base = avg_degree * 6 if src < head else avg_degree
        degree = 1 + next(rnd) % (2 * base)
        seen = set()
        for _ in range(degree):
            r = next(rnd)
            dst = (r % head) if (r & 7) < 3 else (r % n_items)
            if dst == src or dst in seen:
                continue
            seen.add(dst)
            rows.append({"src": src, "dst": dst, "weight": 1 + next(rnd) % 32})
    return rows


def build_embeddings(n_items: int, rnd) -> list[dict]:
    out = []
    for i in range(n_items):
        vec = bytearray(EMBED_DIM)
        norm_sq = 0
        for d in range(EMBED_DIM):
            v = (next(rnd) % 255) - 127
            vec[d] = v & 0xFF
            norm_sq += v * v
        norm = max(1, int(norm_sq ** 0.5))
        out.append({"item_id": i, "dim": EMBED_DIM,
                    "vec": base64.b64encode(bytes(vec)).decode(), "norm": norm})
    return out


def build_users(n_users: int, n_items: int, rnd) -> tuple[list[dict], list[dict]]:
    user_rows, state_rows = [], []
    for uid in range(1, n_users + 1):
        user_rows.append({
            "id": uid,
            "segment": SEGMENTS[next(rnd) % len(SEGMENTS)],
            "region": ("eu", "us", "apac")[next(rnd) % 3],
            "age": 16 + next(rnd) % 60,
            "median_basket_cents": 1_000 + next(rnd) % 50_000,
        })
        recent = [next(rnd) % n_items for _ in range(5 + next(rnd) % 25)]
        purchased = [next(rnd) % n_items for _ in range(20 + next(rnd) % 120)]
        disliked = [next(rnd) % n_items for _ in range(next(rnd) % 15)]
        state_rows.append({
            "user_id": uid,
            "recent_items": ",".join(str(x) for x in recent),
            "purchased_items": ",".join(str(x) for x in purchased),
            "disliked_items": ",".join(str(x) for x in disliked),
        })
    return user_rows, state_rows


def build_pins(n_items: int, rnd) -> list[dict]:
    return [
        {"segment": segment, "slot": slot, "item_id": next(rnd) % n_items}
        for segment in SEGMENTS
        for slot in range(3)
    ]


def build_popularity(n_items: int, rnd) -> list[dict]:
    return [{"item_id": i, "score": next(rnd) % 1_000_000}
            for i in range(min(n_items, 5_000))]


async def seed(n_items: int, n_users: int, avg_degree: int) -> None:
    settings = Settings.from_env()
    engine = create_engine(settings)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(metadata.create_all)
            for table in (impressions, interactions, popularity, pins,
                          item_embeddings, covisitation, user_state, users, items):
                await conn.execute(delete(table))

        rnd = lcg(20260912)
        print(f"items: {n_items}", flush=True)
        await _insert_batched(engine, items, build_items(n_items, rnd))
        print("graph", flush=True)
        graph_rows = build_graph(n_items, avg_degree, rnd)
        await _insert_batched(engine, covisitation, graph_rows)
        print(f"  edges: {len(graph_rows)}", flush=True)
        print("embeddings", flush=True)
        await _insert_batched(engine, item_embeddings, build_embeddings(n_items, rnd))
        print(f"users: {n_users}", flush=True)
        user_rows, state_rows = build_users(n_users, n_items, rnd)
        await _insert_batched(engine, users, user_rows)
        await _insert_batched(engine, user_state, state_rows)
        await _insert_batched(engine, pins, build_pins(n_items, rnd))
        await _insert_batched(engine, popularity, build_popularity(n_items, rnd))

        async with engine.begin() as conn:
            await conn.execute(text("ANALYZE"))
        await verify(engine)
        print("done", flush=True)
    finally:
        await engine.dispose()


async def verify(engine: AsyncEngine) -> None:

    checks = [
        ("items.region_mask", select(func.count(distinct(items.c.region_mask))), 3),
        ("items.stock", select(func.count(distinct(items.c.stock))), 10),
        ("items.created_at", select(func.count(distinct(items.c.created_at))), 100),
        ("items.margin_bps", select(func.count(distinct(items.c.margin_bps))), 1000),
        ("items.active", select(func.count(distinct(items.c.active))), 2),
        ("users.region", select(func.count(distinct(users.c.region))), 3),
        ("users.segment", select(func.count(distinct(users.c.segment))), 4),
    ]
    problems = []
    async with engine.connect() as conn:
        for name, stmt, minimum in checks:
            got = int((await conn.execute(stmt)).scalar() or 0)
            mark = "ok" if got >= minimum else "DEGENERATE"
            print(f"  {name:22s} distinct={got:<7d} need>={minimum:<6d} {mark}",
                  flush=True)
            if got < minimum:
                problems.append(f"{name}: {got} distinct values, expected >= {minimum}")

        for region, bit in (("eu", 1), ("us", 2), ("apac", 4)):
            reachable = int((await conn.execute(
                select(func.count()).where(items.c.region_mask.op("&")(bit) != 0)
            )).scalar() or 0)
            total = int((await conn.execute(select(func.count()).select_from(items))
                        ).scalar() or 0)
            share = reachable / total if total else 0.0
            mark = "ok" if share >= 0.2 else "TOO NARROW"
            print(f"  items visible in {region:<5s} {reachable:<7d} "
                  f"({share:.0%}) {mark}", flush=True)
            if share < 0.2:
                problems.append(f"only {share:.0%} of items visible in {region}")

    if problems:
        raise SystemExit("degenerate fixture:\n  " + "\n  ".join(problems))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--items", type=int, default=100_000)
    ap.add_argument("--users", type=int, default=20_000)
    ap.add_argument("--avg-degree", type=int, default=24)
    args = ap.parse_args()
    asyncio.run(seed(args.items, args.users, args.avg_degree))


if __name__ == "__main__":
    main()
