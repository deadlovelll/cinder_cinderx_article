from __future__ import annotations

from bench.b_async.prime import prime


def lazy_ready(loop, lazy_cls, fn, x: int, n: int):
    v = lazy_cls(fn, x, n)
    loop.run_until_complete(prime(v))
    return v
