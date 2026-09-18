from __future__ import annotations

from fastapi import Request

from recsys.application.use_cases.similar import SimilarUseCase


def similar_use_case(request: Request) -> SimilarUseCase:
    return request.app.state.container.similar
