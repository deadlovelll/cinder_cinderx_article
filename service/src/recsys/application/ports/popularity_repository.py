
from __future__ import annotations

from typing import Protocol, runtime_checkable

from recsys.domain.values.ids import ItemId


@runtime_checkable
class PopularityRepository(Protocol):
    async def top(self, limit: int) -> list[tuple[ItemId, int]]: ...
