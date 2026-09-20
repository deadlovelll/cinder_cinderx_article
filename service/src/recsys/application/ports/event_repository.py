from typing import Protocol, runtime_checkable

from recsys.domain.values.ids import ItemId, UserId


@runtime_checkable
class EventRepository(Protocol):
    async def log_impressions(self, user_id: UserId,
                              item_ids: list[ItemId]) -> None: ...
