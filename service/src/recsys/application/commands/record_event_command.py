from __future__ import annotations

from dataclasses import dataclass

from recsys.domain.values.ids import ItemId, UserId


@dataclass(frozen=True, slots=True)
class RecordEventCommand:
    user_id: UserId
    item_id: ItemId
    kind: str
