from __future__ import annotations

from fastapi import FastAPI


async def shutdown(app: FastAPI) -> None:
    task = getattr(app.state, "gc_task", None)
    if task is not None:
        task.cancel()
    sampler = getattr(app.state, "sampler", None)
    if sampler is not None:
        sampler.stop()
    container = getattr(app.state, "container", None)
    if container is not None:
        await container.aclose()
