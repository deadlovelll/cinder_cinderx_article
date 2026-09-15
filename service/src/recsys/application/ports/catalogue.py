
from __future__ import annotations

from typing import Protocol, runtime_checkable

from recsys.domain.entities.item import Item
from recsys.domain.values.ids import ItemId
from recsys.domain.values.segment import Segment


@runtime_checkable
class Catalogue(Protocol):
    async def load(self) -> None: ...
    def get_many(self, item_ids: list[ItemId]) -> dict[ItemId, Item]: ...
    def pins_for(self, segment: Segment) -> tuple[ItemId, ...]: ...
    def popular(self, limit: int) -> list[tuple[ItemId, int]]: ...
    def size(self) -> int: ...
