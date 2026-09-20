def _close(got: object, expected: object, tol: float) -> tuple[bool, float]:
    if got == expected:
        return True, 0.0
    if isinstance(got, (int, float)) and isinstance(expected, (int, float)):
        dev = abs(got - expected) / max(1.0, abs(expected))
        return dev <= tol, dev
    if isinstance(got, (list, tuple)) and isinstance(expected, (list, tuple)):
        if len(got) != len(expected):
            return False, float("inf")
        worst = 0.0
        for a, b in zip(got, expected, strict=True):
            ok, dev = _close(a, b, tol)
            worst = max(worst, dev)
            if not ok:
                return False, worst
        return True, worst
    return False, float("inf")
