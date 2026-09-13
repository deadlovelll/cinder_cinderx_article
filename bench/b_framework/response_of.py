from __future__ import annotations

import json

from bench.b_framework.constants import SCOPE
from bench.b_framework.receive import _receive


def response_of(app, loop) -> tuple[int, object]:
    sent = []

    async def send(message):
        sent.append(message)

    loop.run_until_complete(app(dict(SCOPE), _receive, send))
    status = next(m["status"] for m in sent if m["type"] == "http.response.start")
    body = b"".join(m.get("body", b"") for m in sent
                    if m["type"] == "http.response.body")
    return status, json.loads(body)
