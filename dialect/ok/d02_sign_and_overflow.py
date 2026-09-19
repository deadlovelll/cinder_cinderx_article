"""The one trap that silently depends on where a value is written."""

import __static__
from __static__ import Array, box, int64


def demo() -> list:
    rows = []
    z: int64 = 0

    rows.append(("box(int64(0) - 8)", box(z - 8)))

    v: int64 = z - 8
    rows.append(("via named local, then box", box(v)))

    rows.append(("(int64(0) - 8) < 0", box((z - 8) < 0)))

    a = Array[int64](4)

    a[0] = z + 8
    rows.append(("Array store, inline positive", box(a[0])))

    a[1] = v
    rows.append(("Array store, negative via local", box(a[1])))

    try:
        a[2] = z - 8
        rows.append(("Array store, negative inline", box(a[2])))
    except OverflowError as exc:
        rows.append(("Array store, negative inline", f"OverflowError: {exc}"))

    return rows
