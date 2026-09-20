from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine


async def count_items(engine: AsyncEngine) -> int:
    async with engine.connect() as conn:
        from recsys.infrastructure.db.tables.items import items

        return int((await conn.execute(select(func.max(items.c.id)))).scalar() or 0) + 1
