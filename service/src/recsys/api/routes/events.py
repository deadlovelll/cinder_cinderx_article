
from fastapi import APIRouter, HTTPException

from recsys.api.dependencies.injected import RecordEventUseCaseDep
from recsys.application.dto.event_payload import EventPayload
from recsys.application.dto.event_response import EventResponse
from recsys.application.use_cases.unknown_kind import UnknownKind

router = APIRouter()


@router.post("/v1/events", response_model=EventResponse, status_code=201)
async def record_event(payload: EventPayload, use_case: RecordEventUseCaseDep) -> dict:
    try:
        weight = await use_case.execute(payload)
    except UnknownKind as exc:
        raise HTTPException(422, f"kind: {exc}") from None
    return {"recorded": True, "weight": weight}
