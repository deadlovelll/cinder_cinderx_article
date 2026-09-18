from __future__ import annotations

from fastapi import Request

from recsys.application.use_cases.record_event import RecordEventUseCase


def record_event_use_case(request: Request) -> RecordEventUseCase:
    return request.app.state.container.record_event
