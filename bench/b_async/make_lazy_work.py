from __future__ import annotations


def make_lazy_work(loop, driver, target, batch: int):
    def work():
        return loop.run_until_complete(driver(target, batch))
    return work
