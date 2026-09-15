
import __static__
from __static__ import Array, box, int64


def from_list(src: list, n: int) -> Array[int64]:
    out = Array[int64](n)
    i: int = 0
    while i < n:
        v: int64 = int64(src[i])
        out[i] = v
        i = i + 1
    return out


def step(cur: Array[int64], nxt: Array[int64], w: int64, h: int64) -> None:
    y: int64 = 0
    while y < h:
        up: int64 = ((y - 1 + h) % h) * w
        mid: int64 = y * w
        dn: int64 = ((y + 1) % h) * w
        x: int64 = 0
        while x < w:
            xl: int64 = (x - 1 + w) % w
            xr: int64 = (x + 1) % w
            n: int64 = (
                cur[up + xl] + cur[up + x] + cur[up + xr]
                + cur[mid + xl] + cur[mid + xr]
                + cur[dn + xl] + cur[dn + x] + cur[dn + xr]
            )
            alive: int64 = cur[mid + x]
            out: int64 = 0
            if n == 3:
                out = 1
            elif n == 2 and alive == 1:
                out = 1
            nxt[mid + x] = out
            x = x + 1
        y = y + 1


def run(grid: Array[int64], scratch: Array[int64], w: int64, h: int64,
        generations: int64) -> Array[int64]:
    cur = grid
    nxt = scratch
    g: int64 = 0
    while g < generations:
        step(cur, nxt, w, h)
        tmp = cur
        cur = nxt
        nxt = tmp
        g = g + 1
    return cur


def checksum(cells: Array[int64], w: int64, h: int64) -> int:
    total: int = 0
    i: int64 = 0
    limit: int64 = w * h
    while i < limit:
        if cells[i] != 0:
            total = (total * 1000003 + box(i)) % (2**61 - 1)
        i = i + 1
    return total
