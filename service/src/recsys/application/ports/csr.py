"""Compressed sparse row adjacency, as a shape rather than a class hierarchy."""

from __future__ import annotations

from typing import Protocol


class CSR(Protocol):
    indptr: object
    indices: object
    weights: object
    n_items: int
