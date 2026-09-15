from __future__ import annotations

import asyncio


def start_lifespan(app, loop) -> None:
    async def receive():
        return {"type": "lifespan.startup"}

    async def send(message):
        pass

    async def go():
        task = asyncio.ensure_future(
            app({"type": "lifespan", "asgi": {"version": "3.0"}}, receive, send))
        await asyncio.sleep(0.05)
        return task

    loop.run_until_complete(go())
