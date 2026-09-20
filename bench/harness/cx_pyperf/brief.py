def _brief(x: object, n: int = 60) -> str:
    s = repr(x)
    return s if len(s) <= n else s[:n] + "..."
