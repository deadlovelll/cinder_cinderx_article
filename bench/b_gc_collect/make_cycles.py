def make_cycles(n: int) -> list:
    out = []
    for _ in range(n // 2):
        a: dict = {}
        b: dict = {"peer": a}
        a["peer"] = b
        out.append(a)
    return out
