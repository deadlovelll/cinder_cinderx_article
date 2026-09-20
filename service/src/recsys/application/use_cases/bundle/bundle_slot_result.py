from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class BundleSlotResult:
    item_id: int
    score: int
    rank: int
    share: float
    label: str
