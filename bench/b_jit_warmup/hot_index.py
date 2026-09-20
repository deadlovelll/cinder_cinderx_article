def hot_index(buf: list, rounds: int) -> int:
    total = 0
    n = len(buf)
    for r in range(rounds):
        i = 0
        while i < n:
            total += buf[i] * buf[n - 1 - i] + r
            i += 1
    return total
