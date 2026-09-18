from __future__ import annotations

from recsys.domain.entities.bundle import Bundle
from recsys.infrastructure.bundles.config import (
    LABELS, SHARE_STEPS, WEIGHT_CAP, WIDTH,
)


class BundleCache:

    def __init__(self, *, items: int, width: int = WIDTH) -> None:
        self._items = items
        self._width = width
        self._bundles: dict[int, Bundle] = {}
        self._tracked = 0
        self._refs = 0

    def size(self) -> int:
        return len(self._bundles)

    def tracked_objects(self) -> int:
        return self._tracked

    def refs(self) -> int:
        return self._refs

    def width(self) -> int:
        return self._width

    def get(self, item_id: int) -> Bundle | None:
        return self._bundles.get(item_id)

    def stats(self) -> dict[str, int]:
        return {"bundles": len(self._bundles), "width": self._width,
                "tracked_objects": self._tracked, "refs": self._refs}

    def warm(self, csr, n_items: int) -> None:
        width = self._width
        indptr, indices, weights = csr.indptr, csr.indices, csr.weights

        ids = list(range(n_items))
        weight_pool = list(range(WEIGHT_CAP))
        rank_pool = list(range(width))
        share_pool = [round(s / SHARE_STEPS, 4) for s in range(SHARE_STEPS)]
        labels = list(LABELS)
        n_labels = len(labels)

        wanted = min(self._items, n_items)
        for item in range(wanted):
            start = int(indptr[item])
            end = int(indptr[item + 1])
            degree = end - start
            if degree <= 0:
                self._bundles[item] = self._synthetic(
                    item, ids, weight_pool, rank_pool, share_pool, labels,
                    n_labels, n_items)
                continue

            neighbours = [0] * width
            column_weights = [0] * width
            ranks = [0] * width
            shares = [0] * width
            column_labels = [0] * width

            total = 0
            for slot in range(width):
                total += int(weights[start + slot % degree])
            if total <= 0:
                total = 1

            for slot in range(width):
                pos = start + slot % degree
                neighbour = int(indices[pos])
                weight = int(weights[pos])
                neighbours[slot] = ids[neighbour]
                column_weights[slot] = weight_pool[weight % WEIGHT_CAP]
                ranks[slot] = rank_pool[slot]
                shares[slot] = share_pool[weight * SHARE_STEPS // total % SHARE_STEPS]
                column_labels[slot] = labels[(neighbour + slot) % n_labels]

            self._bundles[item] = Bundle(neighbours, column_weights, ranks,
                                         shares, column_labels)

        self._tracked = len(self._bundles) * 6
        self._refs = len(self._bundles) * (5 * width + 5)

    def _synthetic(self, item, ids, weight_pool, rank_pool, share_pool,
                   labels, n_labels, n_items) -> Bundle:
        width = self._width
        neighbours = [0] * width
        column_weights = [0] * width
        ranks = [0] * width
        shares = [0] * width
        column_labels = [0] * width
        for slot in range(width):
            neighbour = (item * 31 + slot * 17) % n_items
            neighbours[slot] = ids[neighbour]
            column_weights[slot] = weight_pool[(neighbour + slot) % WEIGHT_CAP]
            ranks[slot] = rank_pool[slot]
            shares[slot] = share_pool[(slot * SHARE_STEPS) // width]
            column_labels[slot] = labels[(neighbour + slot) % n_labels]
        return Bundle(neighbours, column_weights, ranks, shares, column_labels)
