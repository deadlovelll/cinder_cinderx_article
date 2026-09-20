from asyncio import sleep


def spin(x: int, n: int) -> int:
    total = 0
    i = 0
    while i < n:
        total = total + x * i
        i = i + 1
    return total


async def spin_coro(x: int, n: int) -> int:
    total = 0
    i = 0
    while i < n:
        total = total + x * i
        i = i + 1
    return total


async def spin_suspend(x: int, n: int) -> int:
    total = 0
    i = 0
    while i < n:
        total = total + x * i
        i = i + 1
    await sleep(0)
    return total
