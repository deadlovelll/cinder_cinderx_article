import asyncio
import gc
import json
import os
import statistics
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..",
                                "service", "src"))

import cinderx

from recsys.infrastructure.catalogue.memory_catalogue import MemoryCatalogue
from recsys.infrastructure.db.create_engine import create_engine
from recsys.infrastructure.embeddings.numpy_embedding_store import (
    NumpyEmbeddingStore,
)
from recsys.infrastructure.graph.count_items import count_items
from recsys.infrastructure.graph.covisitation_graph import CovisitationGraph
from recsys.settings import Settings

OUT = os.path.join(os.path.dirname(__file__), "prefork_heap.json")
REPS = 7


async def load():
    settings = Settings.from_env()
    engine = create_engine(settings)
    n_items = await count_items(engine)
    graph = CovisitationGraph(engine, n_items)
    await graph.load()
    embeddings = NumpyEmbeddingStore(engine)
    await embeddings.load()
    catalogue = MemoryCatalogue(engine)
    await catalogue.load()
    await engine.dispose()
    return graph, embeddings, catalogue, n_items


def collect_ms() -> float:
    best = float("inf")
    for _ in range(REPS):
        t0 = time.perf_counter()
        gc.collect()
        best = min(best, (time.perf_counter() - t0) * 1e3)
    return best


def main() -> None:
    held = asyncio.run(load())
    n_items = held[3]
    gc.collect()
    tracked = len(gc.get_objects())
    before = collect_ms()
    cinderx.immortalize_heap()
    after = collect_ms()
    print(f"  товаров {n_items}, отслеживаемых объектов {tracked}")
    print(f"  полная сборка до заморозки   {before:7.1f} мс")
    print(f"  полная сборка после заморозки{after:7.1f} мс")
    print(f"  снимает                      {before - after:7.1f} мс")
    json.dump({"items": n_items, "tracked_objects": tracked, "reps": REPS,
               "collect_ms": before, "collect_ms_immortal": after,
               "saved_ms": before - after},
              open(OUT, "w"), indent=1, ensure_ascii=False)
    print("->", OUT)
    del held


if __name__ == "__main__":
    main()
