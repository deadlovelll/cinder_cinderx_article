from dataclasses import dataclass


@dataclass(slots=True)
class LoadedCSR:
    indptr: object
    indices: object
    weights: object
    n_items: int
