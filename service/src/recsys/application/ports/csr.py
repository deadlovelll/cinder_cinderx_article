from typing import Protocol


class CSR(Protocol):
    indptr: object
    indices: object
    weights: object
    n_items: int
