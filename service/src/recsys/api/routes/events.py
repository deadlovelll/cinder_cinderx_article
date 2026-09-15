
from fastapi import APIRouter, HTTPException

from recsys.api.dependencies import Injected
from recsys.application.dto.event_payload import EventPayload
from recsys.application.dto.event_response import EventResponse
from recsys.application.use_cases.record_event import UnknownKind

router = APIRouter()


@router.post("/v1/events", response_model=EventResponse, status_code=201)
async def record_event(payload: EventPayload, container: Injected) -> dict:
    try:
        weight = await container.record_event.execute(payload)
    except UnknownKind as exc:
        raise HTTPException(422, f"kind: {exc}") from None
    return {"recorded": True, "weight": weight}
