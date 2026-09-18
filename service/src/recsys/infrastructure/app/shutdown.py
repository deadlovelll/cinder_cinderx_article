from __future__ import annotations

from fastapi import FastAPI


async def shutdown(app: FastAPI) -> None:
    sampler = getattr(app.state, "sampler", None)
    if sampler is not None:
        sampler.stop()
    container = getattr(app.state, "container", None)
    if container is not None:
        await container.aclose()
