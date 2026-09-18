from __future__ import annotations

from dataclasses import dataclass

from recsys.application.use_cases.bundle.bundle_slot_result import BundleSlotResult


@dataclass(slots=True, frozen=True)
class BundleResult:
    item_id: int
    slots: tuple[BundleSlotResult, ...]
    width: int
    considered: int
