from bench.b_async.prime import prime


def prop_ready(loop, prop_cls, fn, x: int, n: int):

    class Holder:

        @prop_cls
        async def value(self) -> int:
            return await fn(x, n)

    obj = Holder()
    # the first read installs the AsyncLazyValue on the instance
    loop.run_until_complete(prime(obj.value))
    return obj
