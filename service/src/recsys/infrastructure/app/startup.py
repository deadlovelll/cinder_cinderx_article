from __future__ import annotations

import os

from fastapi import FastAPI

from recsys.infrastructure.container.build_container import build
from recsys.infrastructure.bootstrap.after_fork_child import after_fork_child
from recsys.infrastructure.embeddings.embedding_store_impl import embedding_store_impl
from recsys.infrastructure.telemetry.sampler import MetricSampler
from recsys.infrastructure.bootstrap.settings_instance import SETTINGS
from recsys.infrastructure.bundles.bundle_cache import BundleCache
from recsys.infrastructure.graph.count_items import count_items
from recsys.infrastructure.db.create_engine import create_engine
from recsys.infrastructure.graph.covisitation_graph import CovisitationGraph
from recsys.infrastructure.catalogue.memory_catalogue import MemoryCatalogue


async def startup(app: FastAPI) -> None:
    if not hasattr(app.state, "graph"):
        engine = create_engine(SETTINGS)
        n_items = await count_items(engine)
        graph = CovisitationGraph(engine, n_items)
        await graph.load()
        embeddings = embedding_store_impl(SETTINGS)(engine)
        await embeddings.load()
        catalogue = MemoryCatalogue(engine)
        await catalogue.load()
        await engine.dispose()
        app.state.graph = graph
        app.state.embeddings = embeddings
        app.state.catalogue = catalogue

    after_fork_child()

    csr = app.state.graph.csr()
    bundles = BundleCache(items=SETTINGS.bundle_items, width=SETTINGS.bundle_width)
    if SETTINGS.bundle_items > 0:
        bundles.warm(csr, csr.n_items)
    app.state.bundles = bundles

    app.state.container = build(
        SETTINGS, graph=app.state.graph, embeddings=app.state.embeddings,
        catalogue=app.state.catalogue, bundles=bundles)

    sampler_path = os.path.join(SETTINGS.sampler_dir, f"sampler-{os.getpid()}.jsonl")
    app.state.sampler = MetricSampler(
        sampler_path, SETTINGS.sampler_interval_ms,
        context={"config": SETTINGS.as_dict(), "driver": app.state.container.driver})
    app.state.sampler.start()
