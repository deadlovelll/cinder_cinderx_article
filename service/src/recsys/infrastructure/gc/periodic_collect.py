import asyncio
import gc
import time


async def periodic_collect(pauses: dict, interval_ms: int) -> None:
    interval = interval_ms / 1000.0
    while True:
        await asyncio.sleep(interval)
        started = time.perf_counter()
        gc.collect()
        took = (time.perf_counter() - started) * 1e3
        pauses["count"] += 1
        pauses["total_ms"] += took
        pauses["max_ms"] = max(pauses["max_ms"], took)
        pauses["last_ms"] = took
