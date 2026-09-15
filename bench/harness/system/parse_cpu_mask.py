from __future__ import annotations


def parse_cpu_mask(mask: str | None) -> list[int]:
    if not mask:
        return []
    bits = int(mask.replace(",", "").strip() or "0", 16)
    return [c for c in range(bits.bit_length()) if bits >> c & 1]
