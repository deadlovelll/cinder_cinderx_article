from __future__ import annotations


def parse_cpu_list(text: str | None) -> list[int]:
    """Parse the kernel's "0-3,7" CPU list syntax."""
    if not text:
        return []
    out: list[int] = []
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            lo, hi = part.split("-", 1)
            out.extend(range(int(lo), int(hi) + 1))
        else:
            out.append(int(part))
    return sorted(set(out))
