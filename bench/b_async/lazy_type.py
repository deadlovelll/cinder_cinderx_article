from __future__ import annotations


# the native AsyncLazyValue comes from _cinderx; the module also ships a pure
# python fallback, so the caller records which one it got
def lazy_type():
    try:
        from cinderx._asyncio import AsyncLazyValue
    except ImportError:
        return None
    return AsyncLazyValue
