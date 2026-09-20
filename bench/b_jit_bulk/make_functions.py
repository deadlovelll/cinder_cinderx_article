from bench.b_jit_bulk.constants import GEN_MODULE


def make_functions(n: int, salt: str, module: str = GEN_MODULE) -> list:
    ns: dict = {"__name__": module}
    for i in range(n):
        exec(
            f"def f_{salt}_{i}(a, b):\n"
            f"    t = {i}\n"
            f"    for k in range(4):\n"
            f"        t = t + a * {i + 1} - b // {i + 2} + k\n"
            f"        if t > {1000 + i}:\n"
            f"            t = t - {i + 3}\n"
            f"    return t\n",
            ns,
        )
    return [ns[f"f_{salt}_{i}"] for i in range(n)]
