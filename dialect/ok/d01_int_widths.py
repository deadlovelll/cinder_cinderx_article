"""Integer primitives: widths, wraparound, and where they may not appear."""

import __static__
from __static__ import box, int8, int16, int32, int64, uint8, uint64


def demo() -> list:
    rows = []

    a: int64 = 3
    rows.append(("int64 literal, no PyLong built", box(a)))

    wide: int64 = 300
    narrow: int8 = int8(wide)
    rows.append(("int8(int64(300)) -- narrowing wraps", box(narrow)))

    i8: int8 = 127
    i8 = i8 + 1
    rows.append(("int8 127 + 1", box(i8)))

    u8: uint8 = 255
    u8 = u8 + 1
    rows.append(("uint8 255 + 1", box(u8)))

    i16: int16 = 32767
    i16 = i16 + 1
    rows.append(("int16 32767 + 1", box(i16)))

    i32: int32 = 2147483647
    i32 = i32 + 1
    rows.append(("int32 2147483647 + 1", box(i32)))

    big: int64 = (1 << 62)
    rows.append(("int64 holds 1<<62", box(big)))

    u64: uint64 = 0
    u64 = u64 - 1
    rows.append(("uint64 0 - 1 (unsigned wrap)", box(u64)))

    lhs: int8 = 100
    rhs: int64 = 1000
    total: int64 = int64(lhs) + rhs
    rows.append(("int64(int8) + int64", box(total)))

    return rows
