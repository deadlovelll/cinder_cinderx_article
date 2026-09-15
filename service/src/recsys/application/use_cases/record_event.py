
from __future__ import annotations

from recsys.application.dto.event_payload import EventPayload
from recsys.application.ports.event_repository import EventRepository

KINDS = frozenset({"view", "cart", "purchase", "dislike"})
WEIGHTS = {"view": 1, "cart": 3, "purchase": 8, "dislike": -4}


class UnknownKind(Exception):
    pass


class RecordEventUseCase:
    def __init__(self, *, events: EventRepository) -> None:
        self._events = events

    async def execute(self, request: EventPayload) -> int:
        if request.kind not in KINDS:
            raise UnknownKind(request.kind)
        weight = WEIGHTS[request.kind]
        await self._events.record_interaction(
            request.user_id, request.item_id, request.kind, weight)
        return weight
