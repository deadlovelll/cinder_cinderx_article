from __future__ import annotations

from bench.b_framework.constants import BATCH, SCOPE
from bench.b_framework.noop_send import _noop_send
from bench.b_framework.receive import _receive


def make_driver(app, loop):
    async def call():
        i = 0
        while i < BATCH:
            await app(dict(SCOPE), _receive, _noop_send)
            i += 1

    def work():
        loop.run_until_complete(call())
    return work
