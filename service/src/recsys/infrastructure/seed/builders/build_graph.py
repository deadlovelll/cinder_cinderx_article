from __future__ import annotations


def build_graph(n_items: int, avg_degree: int, rnd) -> list[dict]:
    head = max(1, n_items // 100)
    rows = []
    for src in range(n_items):
        base = avg_degree * 6 if src < head else avg_degree
        degree = 1 + next(rnd) % (2 * base)
        seen = set()
        for _ in range(degree):
            r = next(rnd)
            dst = (r % head) if (r & 7) < 3 else (r % n_items)
            if dst == src or dst in seen:
                continue
            seen.add(dst)
            rows.append({"src": src, "dst": dst, "weight": 1 + next(rnd) % 32})
    return rows
