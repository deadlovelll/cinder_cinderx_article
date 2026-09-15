
from __future__ import annotations

import asyncio
import os

bind = "0.0.0.0:8000"
worker_class = "uvicorn.workers.UvicornWorker"
workers = int(os.environ.get("RECSYS_WORKERS", "4"))
preload_app = True

timeout = 120
graceful_timeout = 30
keepalive = 65

max_requests = 0

accesslog = None
errorlog = "-"
loglevel = "info"


def on_starting(server) -> None:
    from recsys.api.app import BOOTSTRAP, SETTINGS, EmbeddingStoreImpl, app
    from recsys.api.bootstrap import prepare_for_fork
    from recsys.infrastructure.db.engine import create_engine
    from recsys.infrastructure.graph import CovisitationGraph, count_items
    from recsys.infrastructure.memory_catalogue import MemoryCatalogue

    async def load() -> tuple[object, object]:
        engine = create_engine(SETTINGS)
        try:
            n_items = await count_items(engine)
            graph = CovisitationGraph(engine, n_items)
            await graph.load()
            embeddings = EmbeddingStoreImpl(engine)
            await embeddings.load()
            catalogue = MemoryCatalogue(engine)
            await catalogue.load()
            return graph, embeddings, catalogue
        finally:
            await engine.dispose()

    graph, embeddings, catalogue = asyncio.run(load())
    app.state.graph = graph
    app.state.embeddings = embeddings
    app.state.catalogue = catalogue

    from recsys.domain.kernels.registry import load_kernel
    from recsys.domain.rules import (
        assemble, backfill, diversity, eligibility, exclusions, hydrate, pins, scoring,
    )

    kernel = load_kernel()
    hot = [
        getattr(kernel, name) for name in ("walk", "reset")
        if hasattr(kernel, name)
    ]
    hot += [fn for fn in (
        getattr(kernel, "take_top", None), getattr(kernel, "take_top_ids", None),
    ) if fn is not None]
    hot += [
        eligibility.apply_eligibility, exclusions.apply_exclusions,
        scoring.apply_scoring, diversity.apply_diversity, pins.apply_pins,
        backfill.apply_backfill, hydrate.hydrate, assemble.to_recommendations,
    ]
    if SETTINGS.embeddings == "static":
        from recsys.domain.kernels import similar_static

        hot += [similar_static.score_all, similar_static.take_top,
                similar_static.boxed_pairs]

    prepare_for_fork(SETTINGS, BOOTSTRAP, hot)

    server.log.info("bootstrap: %s", BOOTSTRAP.as_dict())
    server.log.info("graph edges: %s, catalogue items: %s",
                    graph.loaded_edges(), catalogue.size())
    if BOOTSTRAP.problems:
        for problem in BOOTSTRAP.problems:
            server.log.error("bootstrap problem: %s", problem)


def post_fork(server, worker) -> None:
    from recsys.api.bootstrap import after_fork_child

    after_fork_child()
