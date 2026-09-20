import asyncio
from typing import Any


def dedupe_probe(loop, lazy_cls, waiters: int) -> dict[str, Any]:
    runs = {"naive": 0, "lazy": 0}

    async def body(tag: str) -> int:
        runs[tag] = runs[tag] + 1
        await asyncio.sleep(0)
        return 7

    async def take(v) -> int:
        return await v

    async def plain() -> int:
        return 7

    # a coroutine object is single use, so the naive caller has no choice but
    # to call the function again; this records what it costs him to try
    async def reuse() -> str:
        c = plain()
        await c
        try:
            await c
        except RuntimeError as exc:
            return str(exc)
        return "a coroutine was awaited twice"

    async def probe() -> dict[str, Any]:
        naive = await asyncio.gather(*[body("naive") for _ in range(waiters)])
        v = lazy_cls(body, "lazy")
        lazy = await asyncio.gather(*[take(v) for _ in range(waiters)])
        return {
            "waiters": waiters,
            "naive_body_runs": runs["naive"],
            "lazy_body_runs": runs["lazy"],
            "results_equal": naive == lazy,
            "reuse_error": await reuse(),
        }

    return loop.run_until_complete(probe())
