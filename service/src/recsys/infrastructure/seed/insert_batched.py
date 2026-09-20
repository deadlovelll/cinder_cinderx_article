from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncEngine

from recsys.infrastructure.seed.config import BATCH


async def insert_batched(engine: AsyncEngine, table, rows: list[dict]) -> None:
    stmt = insert(table)
    for start in range(0, len(rows), BATCH):
        async with engine.begin() as conn:
            await conn.execute(stmt, rows[start:start + BATCH])
