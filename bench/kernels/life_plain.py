"""Life on a torus, ordinary Python. The single workload of the configuration ladder."""


def step(cur, nxt, w, h):
    for y in range(h):
        up = ((y - 1) % h) * w
        mid = y * w
        dn = ((y + 1) % h) * w
        for x in range(w):
            xl = (x - 1) % w
            xr = (x + 1) % w
            n = (
                cur[up + xl] + cur[up + x] + cur[up + xr]
                + cur[mid + xl] + cur[mid + xr]
                + cur[dn + xl] + cur[dn + x] + cur[dn + xr]
            )
            alive = cur[mid + x]
            nxt[mid + x] = 1 if (n == 3 or (n == 2 and alive)) else 0


def run(grid, w, h, generations):
    cur = list(grid)
    nxt = [0] * (w * h)
    for _ in range(generations):
        step(cur, nxt, w, h)
        cur, nxt = nxt, cur
    return cur


def checksum(cells, w, h) -> int:
    total = 0
    for i, v in enumerate(cells):
        if v:
            total = (total * 1000003 + i) % (2**61 - 1)
    return total
