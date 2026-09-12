"""Catalogue read. One round trip per request, never one per candidate."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from recsys.domain.entities.item import Item
from recsys.domain.values.ids import ItemId


@runtime_checkable
class ItemRepository(Protocol):
    async def get_many(self, item_ids: list[ItemId]) -> dict[ItemId, Item]: ...
