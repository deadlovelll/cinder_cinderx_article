from recsys.infrastructure.seed.config import MASK


def lcg(seed: int):
    x = seed & MASK
    while True:
        x = (x * 6364136223846793005 + 1442695040888963407) & MASK
        yield x >> 33
