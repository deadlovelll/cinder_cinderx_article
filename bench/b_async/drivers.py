from __future__ import annotations


async def drive_call(fn, x: int, n: int, batch: int) -> int:
    total = 0
    i = 0
    while i < batch:
        total = fn(x, n)
        i = i + 1
    return total


async def drive_await(fn, x: int, n: int, batch: int) -> int:
    total = 0
    i = 0
    while i < batch:
        total = await fn(x, n)
        i = i + 1
    return total


async def drive_ready(v, batch: int) -> int:
    total = 0
    i = 0
    while i < batch:
        total = await v
        i = i + 1
    return total


async def drive_prop(obj, batch: int) -> int:
    total = 0
    i = 0
    while i < batch:
        total = await obj.value
        i = i + 1
    return total
