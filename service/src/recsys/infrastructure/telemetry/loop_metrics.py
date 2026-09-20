import os
from typing import Any


def loop_metrics() -> dict[str, Any]:
    import asyncio

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return {}
    try:
        return {"asyncio_tasks": len(asyncio.all_tasks(loop))}
    except RuntimeError:
        return {}
