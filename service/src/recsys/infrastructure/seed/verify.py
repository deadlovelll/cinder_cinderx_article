from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncEngine

from recsys.infrastructure.db.tables.items import items
from recsys.infrastructure.db.tables.users import users


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
