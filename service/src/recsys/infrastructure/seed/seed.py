from __future__ import annotations

from sqlalchemy import delete, text

from recsys.infrastructure.db.create_engine import create_engine
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
from recsys.infrastructure.seed.builders.build_embeddings import build_embeddings
from recsys.infrastructure.seed.builders.build_graph import build_graph
from recsys.infrastructure.seed.builders.build_items import build_items
from recsys.infrastructure.seed.builders.build_pins import build_pins
from recsys.infrastructure.seed.builders.build_popularity import build_popularity
from recsys.infrastructure.seed.builders.build_users import build_users
from recsys.infrastructure.seed.insert_batched import insert_batched
from recsys.infrastructure.seed.lcg import lcg
from recsys.infrastructure.seed.verify import verify
from recsys.settings import Settings


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
        await insert_batched(engine, items, build_items(n_items, rnd))
        print("graph", flush=True)
        graph_rows = build_graph(n_items, avg_degree, rnd)
        await insert_batched(engine, covisitation, graph_rows)
        print(f"  edges: {len(graph_rows)}", flush=True)
        print("embeddings", flush=True)
        await insert_batched(engine, item_embeddings, build_embeddings(n_items, rnd))
        print(f"users: {n_users}", flush=True)
        user_rows, state_rows = build_users(n_users, n_items, rnd)
        await insert_batched(engine, users, user_rows)
        await insert_batched(engine, user_state, state_rows)
        await insert_batched(engine, pins, build_pins(n_items, rnd))
        await insert_batched(engine, popularity, build_popularity(n_items, rnd))

        async with engine.begin() as conn:
            await conn.execute(text("ANALYZE"))
        await verify(engine)
        print("done", flush=True)
    finally:
        await engine.dispose()
