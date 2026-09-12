"""The write path: interactions and impression counters."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from recsys.domain.values.ids import ItemId, UserId


@runtime_checkable
class EventRepository(Protocol):
    async def record_interaction(self, user_id: UserId, item_id: ItemId,
                                 kind: str, weight: int) -> None: ...

    async def log_impressions(self, user_id: UserId,
                              item_ids: list[ItemId]) -> None: ...
