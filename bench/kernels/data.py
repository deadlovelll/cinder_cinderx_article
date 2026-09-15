
from __future__ import annotations

MASK = (1 << 64) - 1


def lcg(seed: int):
    x = seed & MASK
    while True:
        x = (x * 6364136223846793005 + 1442695040888963407) & MASK
        yield x >> 33


def life_grid(w: int, h: int, fill: int = 30, seed: int = 20260912) -> list[int]:
    rnd = lcg(seed)
    return [1 if next(rnd) % 100 < fill else 0 for _ in range(w * h)]
