
import sys

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter()


@router.get("/healthz")
async def healthz(request: Request) -> JSONResponse:
    state = request.app.state
    container = state.container
    return JSONResponse({
        "status": "ok",
        "python": {"version": sys.version,
                   "implementation": sys.implementation.name,
                   "executable": sys.executable},
        "settings": container.settings.as_dict(),
        "driver": container.driver,
        "bootstrap": state.bootstrap.as_dict(),
        "graph_edges": state.graph.loaded_edges(),
        "catalogue_items": state.catalogue.size(),
        "embeddings": state.embeddings.implementation(),
        "bundle_cache": state.bundles.stats(),
        "gc_pauses": getattr(state, "gc_pauses", None),
    })
