from __future__ import annotations


def make_work(loop, driver, fn, x: int, n: int, batch: int):
    def work():
        return loop.run_until_complete(driver(fn, x, n, batch))
    return work
