"""Return the fixture to the state every rung must start from."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sqlalchemy import func, select, text

from recsys.infrastructure.db.engine import create_engine
from recsys.infrastructure.db.tables.impressions import impressions
from recsys.settings import Settings


async def stats(engine) -> dict:
    """How burned-in the fixture is, in the two numbers that matter."""
    async with engine.connect() as conn:
        total = await conn.scalar(select(func.count()).select_from(impressions))
        users = await conn.scalar(
            select(func.count(func.distinct(impressions.c.user_id))))
        capped = await conn.scalar(
            select(func.count()).select_from(impressions)
            .where(impressions.c.shown >= 3))
    return {"impression_rows": total or 0, "users_with_impressions": users or 0,
            "rows_at_or_over_cap": capped or 0}


async def reset(engine) -> None:
    """TRUNCATE, not DELETE: leave no dead tuples for the next rung to walk past."""
    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE TABLE impressions"))


async def main_async(args) -> int:
    engine = create_engine(Settings.from_env())
    try:
        before = await stats(engine)
        print(f"  до:  {before}")
        if args.reset:
            await reset(engine)
            print(f"  после: {await stats(engine)}")
        elif before["rows_at_or_over_cap"] > 0:
            print("  ВНИМАНИЕ: в фикстуре есть позиции, достигшие предела показов. "
                  "Ступень, запущенная на ней, будет мерить путь backfill.")
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
