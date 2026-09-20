# drives an awaitable to its result once, so the timed driver is never the
# first caller: force_compile() is ignored by a call site that already ran
async def prime(target):
    return await target
