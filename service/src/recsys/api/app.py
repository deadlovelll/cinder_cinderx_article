"""The ASGI application: FastAPI, explicit wiring."""

from __future__ import annotations

import os

from contextlib import asynccontextmanager

from fastapi import FastAPI

from recsys.api import bootstrap
from recsys.api.error_handlers import install_error_handlers
from recsys.api.sampler import MetricSampler
from recsys.settings import Settings

SETTINGS = Settings.from_env()

# steps 1-2 of the pre-fork chain, before the kernels are imported
BOOTSTRAP = bootstrap.install_runtime(SETTINGS)
bootstrap.verify_kernel(BOOTSTRAP)

# imported after the runtime is installed, never before
from recsys.api import container as container_module  # noqa: E402
from recsys.api.routes import events, health, recommend, similar  # noqa: E402
from recsys.infrastructure.graph import CovisitationGraph, count_items  # noqa: E402
from recsys.infrastructure.memory_catalogue import MemoryCatalogue  # noqa: E402

if SETTINGS.embeddings == "numpy":
    from recsys.infrastructure.embeddings_numpy import (  # noqa: E402
        NumpyEmbeddingStore as EmbeddingStoreImpl,
    )
else:
    from recsys.infrastructure.embeddings_python import (  # noqa: E402
        PythonEmbeddingStore as EmbeddingStoreImpl,
    )


async def _startup(app: FastAPI) -> None:
    """Runs per worker. Loads what the parent could not share and builds the engine."""
    from recsys.infrastructure.db.engine import create_engine

    if not hasattr(app.state, "graph"):
        engine = create_engine(SETTINGS)
        n_items = await count_items(engine)
        graph = CovisitationGraph(engine, n_items)
        await graph.load()
        embeddings = EmbeddingStoreImpl(engine)
        await embeddings.load()
        catalogue = MemoryCatalogue(engine)
        await catalogue.load()
        await engine.dispose()
        app.state.graph = graph
        app.state.embeddings = embeddings
        app.state.catalogue = catalogue

    bootstrap.after_fork_child()
    app.state.container = container_module.build(
        SETTINGS, graph=app.state.graph, embeddings=app.state.embeddings,
        catalogue=app.state.catalogue)

    sampler_path = os.path.join(SETTINGS.sampler_dir, f"sampler-{os.getpid()}.jsonl")
    app.state.sampler = MetricSampler(
        sampler_path, SETTINGS.sampler_interval_ms,
        context={"config": SETTINGS.as_dict(), "driver": app.state.container.driver})
    app.state.sampler.start()


async def _shutdown(app: FastAPI) -> None:
    sampler = getattr(app.state, "sampler", None)
    if sampler is not None:
        sampler.stop()
    container = getattr(app.state, "container", None)
    if container is not None:
        await container.aclose()


@asynccontextmanager
async def _lifespan(application: FastAPI):
    """Setup and teardown as one scope: a failed worker is never left half-wired."""
    await _startup(application)
    try:
        yield
    finally:
        await _shutdown(application)


def create_app() -> FastAPI:
    application = FastAPI(
        title="recsys",
        version="1.0.0",
        summary="A recommendation service, used as the workload for measuring CinderX.",
        lifespan=_lifespan,
    )
    install_error_handlers(application)
    for module in (recommend, similar, events, health):
        application.include_router(module.router)
    application.state.bootstrap = BOOTSTRAP
    return application


app = create_app()
