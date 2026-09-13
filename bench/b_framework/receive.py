from __future__ import annotations

from bench.b_framework.constants import BODY


async def _receive():
    return {"type": "http.request", "body": BODY, "more_body": False}
