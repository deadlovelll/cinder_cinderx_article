def prop_type():
    try:
        from cinderx import async_cached_property
    except ImportError:
        return None
    return async_cached_property
