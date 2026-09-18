
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sqlalchemy import func, select, text

from recsys.infrastructure.db.create_engine import create_engine
from recsys.infrastructure.db.tables.impressions import impressions
from recsys.infrastructure.db.tables.interactions import interactions
from recsys.settings import Settings


async def stats(engine) -> dict:
    async with engine.connect() as conn:
        total = await conn.scalar(select(func.count()).select_from(impressions))
        users = await conn.scalar(
            select(func.count(func.distinct(impressions.c.user_id))))
        capped = await conn.scalar(
            select(func.count()).select_from(impressions)
            .where(impressions.c.shown >= 3))
        written = await conn.scalar(select(func.count()).select_from(interactions))
    return {"impression_rows": total or 0, "users_with_impressions": users or 0,
            "rows_at_or_over_cap": capped or 0, "interaction_rows": written or 0}


async def reset(engine) -> None:
    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE TABLE impressions, interactions"))


async def main_async(args) -> int:
    engine = create_engine(Settings.from_env())
    try:
        before = await stats(engine)
        print(f"  before: {before}")
        if args.reset:
            await reset(engine)
            print(f"  after:  {await stats(engine)}")
        elif before["rows_at_or_over_cap"] > 0:
            print("  WARNING: the fixture holds items at the impression cap. A rung "
                  "run on it would measure the backfill path.")
            return 1
        return 0
    finally:
        await engine.dispose()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true",
                    help="truncate impressions; without it the command only reports")
    ap.add_argument("--stats", action="store_true", help="report and exit 0")
    args = ap.parse_args()
    code = asyncio.run(main_async(args))
    raise SystemExit(0 if args.stats else code)


if __name__ == "__main__":
    main()
