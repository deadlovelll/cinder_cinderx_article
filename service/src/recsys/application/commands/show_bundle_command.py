from __future__ import annotations

from dataclasses import dataclass

from recsys.domain.values.ids import ItemId


@dataclass(frozen=True, slots=True)
class ShowBundleCommand:
    item_id: ItemId
    limit: int
