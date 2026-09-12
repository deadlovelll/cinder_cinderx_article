"""Does the JIT help coroutines? (plan: the coroutine axis)"""

from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bench.harness import cx_pyperf as h

h.boot()

DEPTH = 8
BATCH = 500


async def leaf(x: int) -> int:
    return x + 1


async def level_1(x: int) -> int:
    return await leaf(x) + 1


async def level_2(x: int) -> int:
    return await level_1(x) + 1


async def level_3(x: int) -> int:
    return await level_2(x) + 1


async def level_4(x: int) -> int:
    return await level_3(x) + 1


async def level_5(x: int) -> int:
    return await level_4(x) + 1


async def level_6(x: int) -> int:
    return await level_5(x) + 1


async def level_7(x: int) -> int:
    return await level_6(x) + 1


CHAIN = (leaf, level_1, level_2, level_3, level_4, level_5, level_6, level_7)


async def drive_chain(batch: int) -> int:
    total = 0
    i = 0
    while i < batch:
        total += await level_7(i)
        i += 1
    return total


async def drive_gather(batch: int) -> int:
    return sum(await asyncio.gather(*[leaf(i) for i in range(batch)]))


async def drive_sleep0(batch: int) -> int:
    i = 0
    while i < batch:
        await asyncio.sleep(0)
        i += 1
    return i


SHAPES = {
    # shape -> (driver, functions worth compiling, awaits per batch)
    "chain": (drive_chain, (*CHAIN, drive_chain), BATCH * DEPTH),
    "gather": (drive_gather, (leaf, drive_gather), BATCH),
    "sleep0": (drive_sleep0, (drive_sleep0,), BATCH),
}


def main() -> None:
    suite = h.Suite("b_coro", forward=("shape",))
    suite.runner.argparser.add_argument("--shape", choices=tuple(SHAPES),
                                       default="chain")
    args = suite.parse()
    shape = args.shape
    driver, hot, awaits = SHAPES[shape]

    # One loop for the whole run: a loop per measurement would dominate the result.
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    expected = {
        "chain": sum(i + DEPTH for i in range(BATCH)),
        "gather": sum(i + 1 for i in range(BATCH)),
        "sleep0": BATCH,
    }[shape]

    work = lambda: loop.run_until_complete(driver(BATCH))

    if not suite.gate(case="coro", impl=f"{h.config()}/{shape}",
                      got=work(), expected=expected):
        suite.write_sidecar()
        loop.close()
        return

    jit_info = {}
    if h.jit_on():
        jit_info = h.compile_now(*hot, warmup=1, run=work)
        h.jit().get_and_clear_runtime_stats()

    suite.check_once(("coro", shape), work, expected)
    suite.bench(case="coro", impl=f"{h.config()}/{shape}", fn=work,
                params={"batch": BATCH, "depth": DEPTH, "awaits": awaits,
                        "shape": shape},
                inner_loops=awaits,
                note="per-await cost; the loop is reused across measurements")

    suite.machine_probe()

    # Which coroutines the JIT took, and whether the compiled generators survived.
    if h.jit_on():
        jit = h.jit()
        suite.facts["compiled_coroutines"] = {
            fn.__name__: bool(jit.is_jit_compiled(fn)) for fn in hot
        }
        stats = jit.get_and_clear_runtime_stats()
        suite.facts["deopts_after_timing"] = len(stats.get("deopt", []))
        suite.facts["deopt_detail"] = stats.get("deopt", [])[:5]
    coro = driver(0)
    suite.facts["coroutine_type"] = f"{type(coro).__module__}.{type(coro).__name__}"
    coro.close()
    suite.facts["jit"] = jit_info
    suite.write_sidecar()
    loop.close()


if __name__ == "__main__":
    main()
