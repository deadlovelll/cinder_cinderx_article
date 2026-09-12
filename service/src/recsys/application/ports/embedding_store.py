"""Quantised item embeddings, loaded once before the fork."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from recsys.domain.values.ids import ItemId


@runtime_checkable
class EmbeddingStore(Protocol):
    async def load(self) -> None: ...
    def dim(self) -> int: ...
    def similar(self, item_id: ItemId, limit: int) -> list[tuple[ItemId, int]]: ...
    def implementation(self) -> str: ...
